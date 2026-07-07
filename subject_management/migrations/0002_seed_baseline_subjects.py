from django.db import migrations


def seed_subjects(apps, schema_editor):
    Subject = apps.get_model("subject_management", "Subject")

    # Baseline O-Level subjects
    o_level_subjects = [
        ("OL_ENG", "English Language"),
        ("OL_SHO", "Shona"),
        ("OL_MAT", "Mathematics"),
        ("OL_SCI", "Combined Science"),
        ("OL_GEO", "Geography"),
        ("OL_HIS", "History"),
        ("OL_HER", "Heritage Studies"),
        ("OL_FRS", "Family and Religious Studies (FRS)"),
        ("OL_BES", "Business Enterprise Skills"),
        ("OL_POA", "Principles of Accounts"),
        ("OL_AGR", "Agriculture"),
        ("OL_BIO", "Biology"),
        ("OL_CHE", "Chemistry"),
        ("OL_PHY", "Physics"),
    ]

    for code, name in o_level_subjects:
        Subject.objects.get_or_create(
            code=code, defaults={"name": name, "level": "O_LEVEL"}
        )

    # Baseline A-Level subjects
    a_level_subjects = [
        ("AL_ENG", "Literature in English"),
        ("AL_SHO", "Shona"),
        ("AL_MAT", "Mathematics"),
        ("AL_GEO", "Geography"),
        ("AL_HIS", "History"),
        ("AL_HER", "Heritage Studies"),
        ("AL_FRS", "Family and Religious Studies (FRS)"),
        ("AL_BES", "Business Enterprise Skills"),
        ("AL_POA", "Principles of Accounts"),
        ("AL_AGR", "Agriculture"),
        ("AL_BIO", "Biology"),
        ("AL_CHE", "Chemistry"),
        ("AL_PHY", "Physics"),
    ]

    for code, name in a_level_subjects:
        Subject.objects.get_or_create(
            code=code, defaults={"name": name, "level": "A_LEVEL"}
        )


def unload_subjects(apps, schema_editor):
    Subject = apps.get_model("subject_management", "Subject")
    Subject.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        (
            "subject_management",
            "0001_initial",
        ),  # Points to the generated initial migration
    ]

    operations = [
        migrations.RunPython(seed_subjects, reverse_code=unload_subjects),
    ]
