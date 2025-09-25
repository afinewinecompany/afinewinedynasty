from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()


class ProspectResponse(BaseModel):
    id: int
    mlb_id: Optional[str]
    name: str
    position: str
    organization: str
    level: str
    age: int
    eta_year: Optional[int]


@router.get("/", response_model=List[ProspectResponse])
async def get_prospects() -> List[ProspectResponse]:
    # Placeholder data - will be replaced with database queries
    return [
        ProspectResponse(
            id=1,
            mlb_id="123456",
            name="Sample Prospect",
            position="SS",
            organization="Sample Team",
            level="AA",
            age=22,
            eta_year=2025
        )
    ]


@router.get("/{prospect_id}", response_model=ProspectResponse)
async def get_prospect(prospect_id: int) -> ProspectResponse:
    # Placeholder implementation
    return ProspectResponse(
        id=prospect_id,
        mlb_id=f"mlb_{prospect_id}",
        name=f"Prospect {prospect_id}",
        position="CF",
        organization="Sample Organization",
        level="AAA",
        age=21,
        eta_year=2024
    )