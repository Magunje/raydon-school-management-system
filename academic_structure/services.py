from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.core.cache import cache
from django.db import connection, transaction
from django.utils import timezone

from saas_tenant_management.models import get_current_tenant

from .models import AcademicTerm, AcademicYear


SCHOOL_HOLIDAY_LABEL = "School Holiday"
CALENDAR_CACHE_TIMEOUT = 60 * 60 * 6
DEFAULT_ZIMBABWE_TERMS = {
    2026: [
        (1, "Term 1", date(2026, 1, 13), date(2026, 4, 1)),
        (2, "Term 2", date(2026, 5, 12), date(2026, 8, 6)),
        (3, "Term 3", date(2026, 9, 8), date(2026, 12, 8)),
    ],
}


@dataclass
class CalendarSnapshot:
    today: date
    academic_year: AcademicYear | None
    current_term: AcademicTerm | None
    next_term: AcademicTerm | None
    status: str

    @property
    def display_year(self) -> str:
        if self.academic_year:
            return self.academic_year.name or str(self.academic_year.year)
        return str(self.today.year)

    @property
    def display_term(self) -> str:
        if self.current_term:
            return term_display_name(self.current_term)
        return SCHOOL_HOLIDAY_LABEL


def local_today(value: date | None = None) -> date:
    return value or timezone.localdate()


def term_display_name(term: AcademicTerm | None) -> str:
    if term is None:
        return ""
    return term.name or f"Term {term.term_number}"


def _cache_key(on_date: date) -> str:
    tenant = get_current_tenant()
    tenant_key = getattr(tenant, "tenant_id", None) or "global"
    return f"academic-calendar:{tenant_key}:{on_date.isoformat()}"


def _set_status_flags(today: date, dry_run: bool = False) -> None:
    for year in AcademicYear.objects.all():
        if year.start_date and year.end_date:
            if year.start_date <= today <= year.end_date:
                status = "current"
            elif today < year.start_date:
                status = "upcoming"
            else:
                status = "completed"
        elif year.year == today.year:
            status = "current"
        elif year.year > today.year:
            status = "upcoming"
        else:
            status = "completed"
        if not dry_run and year.status != status:
            AcademicYear.objects.filter(pk=year.pk).update(status=status)

    for term in AcademicTerm.objects.select_related("academic_year"):
        if term.start_date and term.end_date:
            if term.start_date <= today <= term.end_date:
                status = "current"
            elif today < term.start_date:
                status = "upcoming"
            else:
                status = "completed"
        else:
            status = "unscheduled"
        if not dry_run and term.status != status:
            AcademicTerm.objects.filter(pk=term.pk).update(status=status)


def ensure_default_calendar(year: int | None = None) -> bool:
    year = int(year or timezone.localdate().year)
    defaults = DEFAULT_ZIMBABWE_TERMS.get(year)
    if not defaults:
        return False

    created = False
    with transaction.atomic():
        academic_year, year_created = AcademicYear.objects.get_or_create(
            year=year,
            defaults={
                "name": str(year),
                "start_date": defaults[0][2],
                "end_date": defaults[-1][3],
                "status": "upcoming",
            },
        )
        if not academic_year.name:
            academic_year.name = str(year)
        if not academic_year.start_date:
            academic_year.start_date = defaults[0][2]
        if not academic_year.end_date:
            academic_year.end_date = defaults[-1][3]
        academic_year.save()
        created = year_created

        for number, name, start_date, end_date in defaults:
            _, term_created = AcademicTerm.objects.get_or_create(
                academic_year=academic_year,
                term_number=number,
                defaults={
                    "name": name,
                    "start_date": start_date,
                    "end_date": end_date,
                    "status": "upcoming",
                },
            )
            created = created or term_created
    return created


def _current_year_for_date(today: date) -> AcademicYear | None:
    return (
        AcademicYear.objects.filter(start_date__lte=today, end_date__gte=today).order_by("year").first()
        or AcademicYear.objects.filter(year=today.year).first()
    )


def _current_term_for_date(today: date) -> AcademicTerm | None:
    return (
        AcademicTerm.objects.select_related("academic_year")
        .filter(start_date__lte=today, end_date__gte=today)
        .order_by("academic_year__year", "term_number")
        .first()
    )


def _next_term_for_date(today: date) -> AcademicTerm | None:
    return (
        AcademicTerm.objects.select_related("academic_year")
        .filter(start_date__gt=today)
        .order_by("start_date", "academic_year__year", "term_number")
        .first()
    )


def _snapshot_for_date(today: date) -> CalendarSnapshot:
    current_term = _current_term_for_date(today)
    academic_year = current_term.academic_year if current_term else _current_year_for_date(today)
    next_term = _next_term_for_date(today)
    return CalendarSnapshot(
        today=today,
        academic_year=academic_year,
        current_term=current_term,
        next_term=next_term,
        status="in_term" if current_term else "holiday",
    )


def _sync_current_flags(snapshot: CalendarSnapshot, dry_run: bool = False) -> None:
    current_year_id = snapshot.academic_year.pk if snapshot.academic_year else None
    current_term_id = snapshot.current_term.pk if snapshot.current_term else None
    if dry_run:
        return

    AcademicYear.objects.exclude(pk=current_year_id).filter(is_current=True).update(is_current=False)
    AcademicTerm.objects.exclude(pk=current_term_id).filter(is_current=True).update(is_current=False)
    AcademicYear.objects.exclude(pk=current_year_id).filter(is_active=True).update(is_active=False)
    AcademicTerm.objects.exclude(pk=current_term_id).filter(is_active=True).update(is_active=False)

    if current_year_id:
        AcademicYear.objects.filter(pk=current_year_id).update(is_current=True, is_active=True, status="current")
    if current_term_id:
        AcademicTerm.objects.filter(pk=current_term_id).update(is_current=True, is_active=True, status="current")


def _update_school_settings(snapshot: CalendarSnapshot, dry_run: bool = False) -> None:
    with connection.cursor() as cursor:
        table_names = connection.introspection.table_names(cursor)
    if "school_settings" not in table_names or dry_run:
        return

    display_term = snapshot.display_term
    display_year = int(snapshot.display_year)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE school_settings
            SET current_term = %s, current_year = %s
            WHERE setting_id = 1
            """,
            [display_term, display_year],
        )


def get_current_academic_year(tenant=None, date: date | None = None):
    return _snapshot_for_date(local_today(date)).academic_year


def get_current_term(tenant=None, date: date | None = None):
    return _snapshot_for_date(local_today(date)).current_term


def sync_current_term(tenant=None, date: date | None = None, dry_run: bool = False) -> CalendarSnapshot:
    today = local_today(date)
    ensure_default_calendar(today.year)
    _set_status_flags(today, dry_run=dry_run)
    snapshot = _snapshot_for_date(today)
    _sync_current_flags(snapshot, dry_run=dry_run)
    _update_school_settings(snapshot, dry_run=dry_run)
    cache.delete(_cache_key(today))
    return snapshot


def current_calendar(date: date | None = None, force_sync: bool = False) -> CalendarSnapshot:
    today = local_today(date)
    cache_key = _cache_key(today)
    cached = cache.get(cache_key)
    if force_sync or not cached:
        snapshot = sync_current_term(date=today)
        cache.set(cache_key, snapshot.display_term, CALENDAR_CACHE_TIMEOUT)
        return snapshot
    return _snapshot_for_date(today)
