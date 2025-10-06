"""
Simple endpoint to retrieve ML predictions from database.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import get_db

router = APIRouter()


@router.get("/predictions")
async def get_all_predictions(
    tier: Optional[str] = Query(None, description="Filter by tier: Star, Solid, Role Player, Org Filler"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence score"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db)
):
    """Get ML predictions for all prospects."""

    # Build query
    where_clauses = ["mp.model_version = 'v1.0'"]

    if tier:
        where_clauses.append(f"mp.predicted_tier = '{tier}'")

    if min_confidence is not None:
        where_clauses.append(f"mp.confidence_score >= {min_confidence}")

    where_clause = " AND ".join(where_clauses)

    query = text(f"""
        SELECT
            p.id,
            p.name,
            p.position,
            mp.predicted_tier,
            mp.predicted_fv,
            mp.confidence_score,
            mp.prediction_date,
            sg.future_value as actual_fv,
            sg.risk_level as actual_risk
        FROM ml_predictions mp
        INNER JOIN prospects p ON p.id = mp.prospect_id
        LEFT JOIN scouting_grades sg ON sg.prospect_id = p.id AND sg.ranking_year = 2024
        WHERE {where_clause}
        ORDER BY mp.predicted_fv DESC, mp.confidence_score DESC
        LIMIT :limit OFFSET :offset
    """)

    result = db.execute(query, {"limit": limit, "offset": offset})
    rows = result.fetchall()

    predictions = []
    for row in rows:
        predictions.append({
            "id": row[0],
            "name": row[1],
            "position": row[2],
            "predicted_tier": row[3],
            "predicted_fv": row[4],
            "confidence_score": float(row[5]) if row[5] else None,
            "prediction_date": row[6].isoformat() if row[6] else None,
            "actual_fv": row[7],
            "actual_risk": row[8]
        })

    # Get total count
    count_query = text(f"""
        SELECT COUNT(*)
        FROM ml_predictions mp
        WHERE {where_clause}
    """)
    total = db.execute(count_query).scalar()

    return {
        "predictions": predictions,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/predictions/{prospect_id}")
async def get_prospect_prediction(
    prospect_id: int,
    db: Session = Depends(get_db)
):
    """Get ML prediction for a specific prospect."""

    query = text("""
        SELECT
            p.id,
            p.name,
            p.position,
            mp.predicted_tier,
            mp.predicted_fv,
            mp.confidence_score,
            mp.prediction_date,
            mp.model_version,
            sg.future_value as actual_fv,
            sg.risk_level as actual_risk,
            sg.hit_future,
            sg.power_future,
            sg.speed_future,
            sg.field_future,
            sg.arm_future
        FROM ml_predictions mp
        INNER JOIN prospects p ON p.id = mp.prospect_id
        LEFT JOIN scouting_grades sg ON sg.prospect_id = p.id AND sg.ranking_year = 2024
        WHERE p.id = :prospect_id
        AND mp.model_version = 'v1.0'
        LIMIT 1
    """)

    result = db.execute(query, {"prospect_id": prospect_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Prediction not found for prospect")

    return {
        "id": row[0],
        "name": row[1],
        "position": row[2],
        "predicted_tier": row[3],
        "predicted_fv": row[4],
        "confidence_score": float(row[5]) if row[5] else None,
        "prediction_date": row[6].isoformat() if row[6] else None,
        "model_version": row[7],
        "actual_fv": row[8],
        "actual_risk": row[9],
        "scouting_grades": {
            "hit_future": row[10],
            "power_future": row[11],
            "speed_future": row[12],
            "field_future": row[13],
            "arm_future": row[14]
        } if row[10] is not None else None
    }


@router.get("/predictions/stats/summary")
async def get_prediction_summary(
    db: Session = Depends(get_db)
):
    """Get summary statistics of all predictions."""

    query = text("""
        SELECT
            predicted_tier,
            COUNT(*) as count,
            AVG(confidence_score) as avg_confidence,
            MIN(confidence_score) as min_confidence,
            MAX(confidence_score) as max_confidence
        FROM ml_predictions
        WHERE model_version = 'v1.0'
        GROUP BY predicted_tier
        ORDER BY
            CASE predicted_tier
                WHEN 'Elite' THEN 1
                WHEN 'Star' THEN 2
                WHEN 'Solid' THEN 3
                WHEN 'Role Player' THEN 4
                WHEN 'Org Filler' THEN 5
            END
    """)

    result = db.execute(query)
    rows = result.fetchall()

    summary = []
    total_predictions = 0

    for row in rows:
        count = row[1]
        total_predictions += count
        summary.append({
            "tier": row[0],
            "count": count,
            "avg_confidence": float(row[2]) if row[2] else None,
            "min_confidence": float(row[3]) if row[3] else None,
            "max_confidence": float(row[4]) if row[4] else None
        })

    # Add percentages
    for item in summary:
        item["percentage"] = (item["count"] / total_predictions * 100) if total_predictions > 0 else 0

    return {
        "summary": summary,
        "total_predictions": total_predictions,
        "model_version": "v1.0"
    }


@router.get("/predictions/top/{limit}")
async def get_top_predictions(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get top predicted prospects."""

    if limit > 100:
        limit = 100

    query = text("""
        SELECT
            p.id,
            p.name,
            p.position,
            mp.predicted_tier,
            mp.predicted_fv,
            mp.confidence_score,
            sg.future_value as actual_fv
        FROM ml_predictions mp
        INNER JOIN prospects p ON p.id = mp.prospect_id
        LEFT JOIN scouting_grades sg ON sg.prospect_id = p.id AND sg.ranking_year = 2024
        WHERE mp.model_version = 'v1.0'
        ORDER BY mp.predicted_fv DESC, mp.confidence_score DESC
        LIMIT :limit
    """)

    result = db.execute(query, {"limit": limit})
    rows = result.fetchall()

    predictions = []
    for row in rows:
        predictions.append({
            "id": row[0],
            "name": row[1],
            "position": row[2],
            "predicted_tier": row[3],
            "predicted_fv": row[4],
            "confidence_score": float(row[5]) if row[5] else None,
            "actual_fv": row[6]
        })

    return {
        "top_predictions": predictions,
        "limit": limit
    }
