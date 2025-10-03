"""
@fileoverview Pydantic schemas for onboarding API endpoints

Defines request and response models for user onboarding flow operations.

@module OnboardingSchemas
@version 1.0.0
@author A Fine Wine Dynasty Team
@since 1.0.0
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class OnboardingStatus(BaseModel):
    """
    Onboarding status response model

    @interface OnboardingStatus
    @since 1.0.0
    """
    user_id: int = Field(..., description="User ID")
    current_step: int = Field(..., ge=0, description="Current onboarding step (0-indexed)")
    current_step_name: str = Field(..., description="Name of current onboarding step")
    total_steps: int = Field(..., description="Total number of onboarding steps")
    is_completed: bool = Field(..., description="Whether onboarding has been completed")
    progress_percentage: float = Field(..., ge=0, le=100, description="Onboarding progress percentage")
    started_at: Optional[str] = Field(None, description="ISO timestamp when onboarding started")
    completed_at: Optional[str] = Field(None, description="ISO timestamp when onboarding completed")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123,
                "current_step": 2,
                "current_step_name": "feature_tour_profiles",
                "total_steps": 6,
                "is_completed": False,
                "progress_percentage": 33.33,
                "started_at": "2025-10-03T10:00:00",
                "completed_at": None
            }
        }


class OnboardingProgressRequest(BaseModel):
    """
    Request model for progressing onboarding step

    @interface OnboardingProgressRequest
    @since 1.0.0
    """
    step: int = Field(..., ge=0, description="Step number to progress to (0-indexed)")

    class Config:
        json_schema_extra = {
            "example": {
                "step": 3
            }
        }


class OnboardingCompletionResponse(BaseModel):
    """
    Response model for onboarding completion

    @interface OnboardingCompletionResponse
    @since 1.0.0
    """
    user_id: int = Field(..., description="User ID")
    is_completed: bool = Field(..., description="Completion status")
    completed_at: str = Field(..., description="ISO timestamp of completion")
    message: str = Field(..., description="Completion message")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123,
                "is_completed": True,
                "completed_at": "2025-10-03T10:30:00",
                "message": "Onboarding completed successfully"
            }
        }


class OnboardingResetResponse(BaseModel):
    """
    Response model for onboarding reset

    @interface OnboardingResetResponse
    @since 1.0.0
    """
    user_id: int = Field(..., description="User ID")
    current_step: int = Field(..., description="Reset step (always 0)")
    is_completed: bool = Field(..., description="Completion status (always False)")
    message: str = Field(..., description="Reset confirmation message")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123,
                "current_step": 0,
                "is_completed": False,
                "message": "Onboarding reset successfully"
            }
        }
