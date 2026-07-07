from django.core.management.base import BaseCommand

from students.services import backfill_realistic_student_photos


class Command(BaseCommand):
    help = "Generate realistic, age-appropriate student profile photos for pupils who do not have one."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of student photos to generate.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate photos even for students who already have them.",
        )

    def handle(self, *args, **options):
        limit = options.get("limit")
        force = options.get("force")
        
        self.stdout.write("Scanning students and generating realistic photos...")
        updated = backfill_realistic_student_photos(limit=limit, force=force)
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed and generated realistic photos for {updated} student(s)."
            )
        )
