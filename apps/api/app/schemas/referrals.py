"""
Pydantic schemas for referral operations.

@module referrals
@since 1.0.0
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ReferralCodeResponse(BaseModel):
    """Schema for referral code API response."""
    id: int
    user_id: int
    code: str
    uses_remaining: int
    created_at: datetime

    class Config:
        from_attributes = True


class ReferralStatsResponse(BaseModel):
    """Schema for referral statistics."""
    total_referrals: int
    successful_referrals: int
    pending_referrals: int
    rewards_earned: int
    referral_code: str


class GenerateReferralCodeRequest(BaseModel):
    """Schema for generating new referral code."""
    pass  # No parameters needed, user from auth


class ValidateReferralCodeRequest(BaseModel):
    """Schema for validating referral code during signup."""
    code: str
