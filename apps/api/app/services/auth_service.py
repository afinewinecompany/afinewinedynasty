# Legacy module for backward compatibility
# All functionality has been moved to user_service.py to use database persistence

from app.services.user_service import (
    get_user_by_email,
    create_user,
    authenticate_user,
    get_generic_error_message
)

# Re-export for backward compatibility
__all__ = ["get_user_by_email", "create_user", "authenticate_user", "get_generic_error_message"]