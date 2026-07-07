from django.core.management.base import BaseCommand

from students.services import backfill_student_portraits


class Command(BaseCommand):
    help = "Generate illustrated student portraits for pupil records that do not have a photo."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Maximum number of student portraits to generate.")

    def handle(self, *args, **options):
        updated = backfill_student_portraits(limit=options.get("limit"))
        self.stdout.write(self.style.SUCCESS(f"Generated {updated} student portrait(s)."))
