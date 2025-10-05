"""Pydantic models for Scouting Grades data validation."""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class ScoutingGradesBase(BaseModel):
    """Base model for scouting grades validation (20-80 scale)."""

    prospect_id: int = Field(..., description="Reference to prospect")
    source: str = Field(..., max_length=50, description="Source of scouting grade")
    overall_grade: Optional[float] = Field(None, ge=20, le=80)
    hit_grade: Optional[float] = Field(None, ge=20, le=80)
    power_grade: Optional[float] = Field(None, ge=20, le=80)
    speed_grade: Optional[float] = Field(None, ge=20, le=80)
    field_grade: Optional[float] = Field(None, ge=20, le=80)
    arm_grade: Optional[float] = Field(None, ge=20, le=80)
    date_recorded: datetime = Field(..., description="When grades were recorded")

    @field_validator('source')
    @classmethod
    def validate_source(cls, v):
        """Validate and standardize scouting source."""
        source_map = {
            'fg': 'Fangraphs',
            'ba': 'Baseball America',
            'bp': 'Baseball Prospectus',
            'mlb': 'MLB Pipeline',
            'keith law': 'Keith Law',
            'the athletic': 'The Athletic'
        }
        return source_map.get(v.lower(), v)

    @field_validator('overall_grade', 'hit_grade', 'power_grade', 'speed_grade', 'field_grade', 'arm_grade')
    @classmethod
    def validate_grade_scale(cls, v):
        """Ensure grades are on 20-80 scale."""
        if v is not None:
            # Convert common alternative scales
            if v <= 10:
                # 2-8 scale to 20-80
                return v * 10
            elif v > 80:
                # 0-100 scale to 20-80
                return 20 + (v / 100) * 60

            # Round to nearest 5 for standard scouting grades
            return round(v / 5) * 5
        return v

    def calculate_overall_if_missing(self):
        """Calculate overall grade if missing based on tool grades."""
        if self.overall_grade is None:
            grades = [
                self.hit_grade,
                self.power_grade,
                self.speed_grade,
                self.field_grade,
                self.arm_grade
            ]
            valid_grades = [g for g in grades if g is not None]
            if valid_grades:
                # Weight hitting tools slightly more for position players
                if self.hit_grade and self.power_grade:
                    weighted_sum = (
                        (self.hit_grade or 0) * 1.5 +
                        (self.power_grade or 0) * 1.5 +
                        (self.speed_grade or 0) +
                        (self.field_grade or 0) +
                        (self.arm_grade or 0)
                    )
                    weight_total = sum([
                        1.5 if self.hit_grade else 0,
                        1.5 if self.power_grade else 0,
                        1 if self.speed_grade else 0,
                        1 if self.field_grade else 0,
                        1 if self.arm_grade else 0
                    ])
                    if weight_total > 0:
                        self.overall_grade = round(weighted_sum / weight_total / 5) * 5
                else:
                    self.overall_grade = round(sum(valid_grades) / len(valid_grades) / 5) * 5

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "prospect_id": 1,
                "source": "Fangraphs",
                "overall_grade": 55,
                "hit_grade": 60,
                "power_grade": 50,
                "speed_grade": 55,
                "field_grade": 45,
                "arm_grade": 50,
                "date_recorded": "2025-01-15T00:00:00"
            }
        }


class ScoutingGradesCreate(ScoutingGradesBase):
    """Model for creating new scouting grades."""

    def __init__(self, **data):
        super().__init__(**data)
        self.calculate_overall_if_missing()


class ScoutingGradesUpdate(BaseModel):
    """Model for updating scouting grades."""

    source: Optional[str] = Field(None, max_length=50)
    overall_grade: Optional[float] = Field(None, ge=20, le=80)
    hit_grade: Optional[float] = Field(None, ge=20, le=80)
    power_grade: Optional[float] = Field(None, ge=20, le=80)
    speed_grade: Optional[float] = Field(None, ge=20, le=80)
    field_grade: Optional[float] = Field(None, ge=20, le=80)
    arm_grade: Optional[float] = Field(None, ge=20, le=80)


class ScoutingGradesInDB(ScoutingGradesBase):
    """Model for scouting grades from database."""

    id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


class ScoutingGradesConsensus(BaseModel):
    """Model for consensus scouting grades across sources."""

    prospect_id: int
    sources_count: int
    avg_overall_grade: float
    std_overall_grade: float
    avg_hit_grade: Optional[float]
    avg_power_grade: Optional[float]
    avg_speed_grade: Optional[float]
    avg_field_grade: Optional[float]
    avg_arm_grade: Optional[float]
    latest_grade: float
    highest_grade: float
    lowest_grade: float