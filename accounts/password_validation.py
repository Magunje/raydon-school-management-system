import re

from django.core.exceptions import ValidationError


PASSWORD_MIN_LENGTH = 8


def validate_password_strength(password):
    password = password or ""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValidationError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if not re.search(r"[A-Za-z]", password):
        raise ValidationError("Password must include at least one letter.")
    if not re.search(r"\d", password):
        raise ValidationError("Password must include at least one number.")


class LetterNumberPasswordValidator:
    def validate(self, password, user=None):
        validate_password_strength(password)

    def get_help_text(self):
        return f"Your password must be at least {PASSWORD_MIN_LENGTH} characters and include letters and numbers."
