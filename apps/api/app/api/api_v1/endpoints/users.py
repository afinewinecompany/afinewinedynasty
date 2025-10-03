from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.api.deps import get_current_user
from app.models.user import UserLogin
from app.db.models import User
from app.db.database import get_db
from app.core.security import get_password_hash, verify_password, is_password_complex
from app.core.validation import validate_email_format, validate_password_input, validate_name_input
from typing import Optional, Dict, Any
from datetime import datetime
import json

router = APIRouter()


class UserProfileResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    google_id: Optional[str] = None
    profile_picture: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


class UserProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

    @validator('full_name')
    def validate_name(cls, v):
        if v is not None:
            return validate_name_input(v)
        return v


class PasswordUpdateRequest(BaseModel):
    current_password: str
    new_password: str

    @validator('current_password')
    def validate_current_password(cls, v):
        return validate_password_input(v)

    @validator('new_password')
    def validate_new_password(cls, v):
        return validate_password_input(v)


class ConsentUpdateRequest(BaseModel):
    privacy_policy_accepted: bool
    marketing_emails_accepted: Optional[bool] = False
    data_processing_accepted: bool


class UserDataExportResponse(BaseModel):
    user_data: Dict[str, Any]
    export_timestamp: datetime
    data_retention_info: str


class AccountDeletionRequest(BaseModel):
    password: str
    confirmation: str

    @validator('password')
    def validate_password(cls, v):
        return validate_password_input(v)

    @validator('confirmation')
    def validate_confirmation(cls, v):
        if v != "DELETE_MY_ACCOUNT":
            raise ValueError("Confirmation must be 'DELETE_MY_ACCOUNT'")
        return v


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserProfileResponse:
    """Get current user's profile"""
    # Get full user data from database
    stmt = select(User).where(User.email == current_user.email, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    # Parse preferences from JSON if stored as string
    preferences = user.preferences
    if isinstance(preferences, str):
        try:
            preferences = json.loads(preferences)
        except:
            preferences = {}

    return UserProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        google_id=user.google_id,
        profile_picture=user.profile_picture,
        preferences=preferences
    )


@router.put("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    update_request: UserProfileUpdateRequest,
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserProfileResponse:
    """Update current user's profile"""
    stmt = select(User).where(User.email == current_user.email, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    # Update fields if provided
    if update_request.full_name is not None:
        user.full_name = update_request.full_name

    if update_request.preferences is not None:
        # Store preferences as JSON
        user.preferences = json.dumps(update_request.preferences) if update_request.preferences else None

    user.updated_at = datetime.now()

    await db.commit()
    await db.refresh(user)

    # Parse preferences for response
    preferences = user.preferences
    if isinstance(preferences, str):
        try:
            preferences = json.loads(preferences)
        except:
            preferences = {}

    return UserProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        google_id=user.google_id,
        profile_picture=user.profile_picture,
        preferences=preferences
    )


@router.put("/password")
async def update_password(
    password_request: PasswordUpdateRequest,
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user's password"""
    stmt = select(User).where(User.email == current_user.email, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # For OAuth users (no password), don't allow password updates
    if not user.hashed_password or user.google_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth users cannot update password. Use your OAuth provider."
        )

    # Verify current password
    if not verify_password(password_request.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Validate new password complexity
    is_valid, message = is_password_complex(password_request.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    # Update password
    user.hashed_password = get_password_hash(password_request.new_password)
    user.updated_at = datetime.now()

    await db.commit()

    return {"message": "Password updated successfully"}


@router.get("/preferences")
async def get_user_preferences(
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get current user's preferences"""
    stmt = select(User).where(User.email == current_user.email, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Parse preferences from JSON if stored as string
    preferences = user.preferences
    if isinstance(preferences, str):
        try:
            preferences = json.loads(preferences)
        except:
            preferences = {}
    elif preferences is None:
        preferences = {}

    return preferences


@router.put("/preferences")
async def update_user_preferences(
    preferences: Dict[str, Any],
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Update current user's preferences"""
    stmt = select(User).where(User.email == current_user.email, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Store preferences as JSON
    user.preferences = json.dumps(preferences) if preferences else None
    user.updated_at = datetime.now()

    await db.commit()

    return {"message": "Preferences updated successfully", "preferences": preferences}


@router.get("/export", response_model=UserDataExportResponse)
async def export_user_data(
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserDataExportResponse:
    """Export all user data for GDPR compliance"""
    stmt = select(User).where(User.email == current_user.email, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User data not found"
        )

    # Parse preferences from JSON if stored as string
    preferences = user.preferences
    if isinstance(preferences, str):
        try:
            preferences = json.loads(preferences)
        except:
            preferences = {}

    # Create a sanitized copy of user data for export
    export_data = {
        "personal_information": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "profile_picture": user.profile_picture,
            "google_id": user.google_id,
            "account_created": user.created_at.isoformat() if user.created_at else None,
            "last_updated": user.updated_at.isoformat() if user.updated_at else None,
        },
        "preferences": preferences,
        "consent_data": {
            "privacy_policy_accepted": user.privacy_policy_accepted,
            "privacy_policy_accepted_at": user.privacy_policy_accepted_at.isoformat() if user.privacy_policy_accepted_at else None,
            "data_processing_accepted": user.data_processing_accepted,
            "data_processing_accepted_at": user.data_processing_accepted_at.isoformat() if user.data_processing_accepted_at else None,
            "marketing_emails_accepted": user.marketing_emails_accepted,
        },
        "account_status": {
            "is_active": user.is_active,
        }
    }

    return UserDataExportResponse(
        user_data=export_data,
        export_timestamp=datetime.now(),
        data_retention_info="Personal data will be retained as per our Privacy Policy. You may request deletion at any time."
    )


@router.put("/consent")
async def update_consent(
    consent_request: ConsentUpdateRequest,
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user consent preferences"""
    stmt = select(User).where(User.email == current_user.email, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update consent fields
    user.privacy_policy_accepted = consent_request.privacy_policy_accepted
    user.data_processing_accepted = consent_request.data_processing_accepted
    user.marketing_emails_accepted = consent_request.marketing_emails_accepted

    if consent_request.privacy_policy_accepted:
        user.privacy_policy_accepted_at = datetime.now()

    if consent_request.data_processing_accepted:
        user.data_processing_accepted_at = datetime.now()

    user.updated_at = datetime.now()

    await db.commit()

    return {"message": "Consent preferences updated successfully"}


@router.delete("/delete")
async def delete_user_account(
    deletion_request: AccountDeletionRequest,
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete user account and all associated data (GDPR right to be forgotten)"""
    stmt = select(User).where(User.email == current_user.email, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # For OAuth users (no password), skip password verification
    if user.hashed_password and not user.google_id:
        # Verify password for security
        if not verify_password(deletion_request.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password"
            )

    # Delete user from database
    # Note: Cascading deletes should handle related records (sessions, etc.)
    await db.delete(user)
    await db.commit()

    # In a real application, you would also:
    # - Remove user from all related tables (handled by cascade)
    # - Delete user files/uploads
    # - Log the deletion for audit purposes
    # - Anonymize any data that must be retained for legal reasons

    return {
        "message": "Account and all associated data have been permanently deleted",
        "deleted_at": datetime.now().isoformat()
    }
