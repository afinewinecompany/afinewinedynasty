from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, validator
from app.api.deps import get_current_user
from app.models.user import UserLogin, UserInDB
from app.services.auth_service import get_user_by_email, fake_users_db
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
async def get_user_profile(current_user: UserLogin = Depends(get_current_user)) -> UserProfileResponse:
    """Get current user's profile"""
    # Get full user data from fake_users_db
    user_data = fake_users_db.get(current_user.email)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    return UserProfileResponse(
        id=user_data["id"],
        email=user_data["email"],
        full_name=user_data["full_name"],
        is_active=user_data["is_active"],
        created_at=user_data.get("created_at", datetime.now()),
        updated_at=user_data.get("updated_at", datetime.now()),
        google_id=user_data.get("google_id"),
        profile_picture=user_data.get("profile_picture"),
        preferences=user_data.get("preferences", {})
    )


@router.put("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    update_request: UserProfileUpdateRequest,
    current_user: UserLogin = Depends(get_current_user)
) -> UserProfileResponse:
    """Update current user's profile"""
    user_data = fake_users_db.get(current_user.email)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    # Update fields if provided
    if update_request.full_name is not None:
        user_data["full_name"] = update_request.full_name

    if update_request.preferences is not None:
        user_data["preferences"] = update_request.preferences

    user_data["updated_at"] = datetime.now()

    return UserProfileResponse(
        id=user_data["id"],
        email=user_data["email"],
        full_name=user_data["full_name"],
        is_active=user_data["is_active"],
        created_at=user_data.get("created_at", datetime.now()),
        updated_at=user_data["updated_at"],
        google_id=user_data.get("google_id"),
        profile_picture=user_data.get("profile_picture"),
        preferences=user_data.get("preferences", {})
    )


@router.put("/password")
async def update_password(
    password_request: PasswordUpdateRequest,
    current_user: UserLogin = Depends(get_current_user)
):
    """Update user's password"""
    user_data = fake_users_db.get(current_user.email)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # For OAuth users (no password), don't allow password updates
    if not user_data.get("hashed_password"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth users cannot update password. Use your OAuth provider."
        )

    # Verify current password
    if not verify_password(password_request.current_password, user_data["hashed_password"]):
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
    user_data["hashed_password"] = get_password_hash(password_request.new_password)
    user_data["updated_at"] = datetime.now()

    return {"message": "Password updated successfully"}


@router.get("/preferences")
async def get_user_preferences(current_user: UserLogin = Depends(get_current_user)) -> Dict[str, Any]:
    """Get current user's preferences"""
    user_data = fake_users_db.get(current_user.email)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user_data.get("preferences", {})


@router.put("/preferences")
async def update_user_preferences(
    preferences: Dict[str, Any],
    current_user: UserLogin = Depends(get_current_user)
) -> Dict[str, Any]:
    """Update current user's preferences"""
    user_data = fake_users_db.get(current_user.email)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user_data["preferences"] = preferences
    user_data["updated_at"] = datetime.now()

    return {"message": "Preferences updated successfully", "preferences": preferences}


@router.get("/export", response_model=UserDataExportResponse)
async def export_user_data(current_user: UserLogin = Depends(get_current_user)) -> UserDataExportResponse:
    """Export all user data for GDPR compliance"""
    user_data = fake_users_db.get(current_user.email)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User data not found"
        )

    # Create a sanitized copy of user data for export
    export_data = {
        "personal_information": {
            "id": user_data["id"],
            "email": user_data["email"],
            "full_name": user_data["full_name"],
            "profile_picture": user_data.get("profile_picture"),
            "google_id": user_data.get("google_id"),
            "account_created": user_data.get("created_at").isoformat() if user_data.get("created_at") else None,
            "last_updated": user_data.get("updated_at").isoformat() if user_data.get("updated_at") else None,
        },
        "preferences": user_data.get("preferences", {}),
        "consent_data": {
            "privacy_policy_accepted": user_data.get("privacy_policy_accepted"),
            "privacy_policy_accepted_at": user_data.get("privacy_policy_accepted_at").isoformat() if user_data.get("privacy_policy_accepted_at") else None,
            "data_processing_accepted": user_data.get("data_processing_accepted"),
            "data_processing_accepted_at": user_data.get("data_processing_accepted_at").isoformat() if user_data.get("data_processing_accepted_at") else None,
            "marketing_emails_accepted": user_data.get("marketing_emails_accepted"),
        },
        "account_status": {
            "is_active": user_data["is_active"],
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
    current_user: UserLogin = Depends(get_current_user)
):
    """Update user consent preferences"""
    user_data = fake_users_db.get(current_user.email)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update consent fields
    user_data["privacy_policy_accepted"] = consent_request.privacy_policy_accepted
    user_data["data_processing_accepted"] = consent_request.data_processing_accepted
    user_data["marketing_emails_accepted"] = consent_request.marketing_emails_accepted

    if consent_request.privacy_policy_accepted:
        user_data["privacy_policy_accepted_at"] = datetime.now()

    if consent_request.data_processing_accepted:
        user_data["data_processing_accepted_at"] = datetime.now()

    user_data["updated_at"] = datetime.now()

    return {"message": "Consent preferences updated successfully"}


@router.delete("/delete")
async def delete_user_account(
    deletion_request: AccountDeletionRequest,
    current_user: UserLogin = Depends(get_current_user)
):
    """Delete user account and all associated data (GDPR right to be forgotten)"""
    user_data = fake_users_db.get(current_user.email)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # For OAuth users (no password), skip password verification
    if user_data.get("hashed_password"):
        # Verify password for security
        if not verify_password(deletion_request.password, user_data["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password"
            )

    # Delete all user data
    del fake_users_db[current_user.email]

    # In a real application, you would also:
    # - Remove user from all related tables
    # - Delete user files/uploads
    # - Log the deletion for audit purposes
    # - Anonymize any data that must be retained for legal reasons

    return {
        "message": "Account and all associated data have been permanently deleted",
        "deleted_at": datetime.now().isoformat()
    }