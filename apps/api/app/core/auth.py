"""Authentication utilities for API endpoints."""

from typing import Optional
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..api.deps import get_current_user as _get_current_user
from ..models.user import UserLogin

# Re-export for convenience
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> UserLogin:
    """Get current authenticated user."""
    return _get_current_user(credentials)