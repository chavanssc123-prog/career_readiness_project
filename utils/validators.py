import re


def is_valid_email(email: str) -> bool:
    if not email:
        return False
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    return bool(re.match(pattern, email))


def validate_registration(name: str, email: str, password: str, confirm_password: str) -> list:
    errors = []

    if not name.strip():
        errors.append("Full Name is required.")

    if not email.strip():
        errors.append("Email address is required.")
    elif not is_valid_email(email):
        errors.append("Please enter a valid email address.")

    if not password:
        errors.append("Password is required.")
    elif len(password) < 8:
        errors.append("Password must be at least 8 characters long.")

    if password != confirm_password:
        errors.append("Password and Confirm Password must match.")

    return errors
