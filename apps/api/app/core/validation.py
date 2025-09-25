import re
from typing import Any
from fastapi import HTTPException, status


def sanitize_string(value: str, max_length: int = 255) -> str:
    """Sanitize string input"""
    if not isinstance(value, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input type"
        )

    # Check length
    if len(value) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input too long (max {max_length} characters)"
        )

    # Remove null bytes and control characters (except newlines and tabs)
    sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)

    # Strip leading/trailing whitespace
    sanitized = sanitized.strip()

    return sanitized


def validate_email_format(email: str) -> str:
    """Validate email format with additional checks"""
    # Basic email pattern check
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    if not email_pattern.match(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )

    # Check for common injection patterns
    dangerous_patterns = [
        r'<script',
        r'javascript:',
        r'vbscript:',
        r'onload=',
        r'onerror=',
        r'<iframe',
        r'<object',
        r'<embed'
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, email, re.IGNORECASE):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )

    return email.lower()


def validate_password_input(password: str) -> str:
    """Validate password input"""
    if not isinstance(password, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password format"
        )

    # Check length limits
    if len(password) < 8 or len(password) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be between 8 and 128 characters"
        )

    # Check for null bytes
    if '\x00' in password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password format"
        )

    return password


def validate_name_input(name: str) -> str:
    """Validate name input"""
    name = sanitize_string(name, max_length=100)

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name cannot be empty"
        )

    # Allow only letters, spaces, hyphens, and apostrophes
    if not re.match(r"^[a-zA-Z\s\-']+$", name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name contains invalid characters"
        )

    return name