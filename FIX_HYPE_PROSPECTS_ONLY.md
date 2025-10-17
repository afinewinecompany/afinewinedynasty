# Fix: Hype Leaderboard Should Only Show Prospects

## Current Issue

The HYPE leaderboard currently shows:
- **100 prospects** (correct)
- **3 MLB players** (incorrect - Shohei Ohtani, Aaron Judge, Paul Skenes from demo testing)

## Solution

Update the hype leaderboard API to filter by `player_type = 'prospect'` only.

## Implementation

### Backend Fix (API)

File: `apps/api/app/routers/hype.py`

Update the `/leaderboard` endpoint to filter prospects only:

```python
@router.get("/leaderboard", response_model=List[HypeLeaderboardItem])
async def get_hype_leaderboard(
    player_type: Optional[str] = None,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get HYPE leaderboard (public endpoint)"""

    stmt = select(PlayerHype)

    # ALWAYS filter to prospects only for leaderboard
    # (Frontend can still request 'mlb' type for other purposes)
    if player_type == 'mlb':
        stmt = stmt.filter(PlayerHype.player_type == 'mlb')
    else:
        # Default to prospects only
        stmt = stmt.filter(PlayerHype.player_type == 'prospect')

    stmt = stmt.order_by(desc(PlayerHype.hype_score)).limit(limit)
    # ...rest of code
```

## Testing

After fix:
```bash
# Should return only prospects
GET /api/v1/hype/leaderboard?limit=100

# Verify count
python -c "
from app.db.database import SyncSessionLocal
from app.models.hype import PlayerHype
db = SyncSessionLocal()
prospects = db.query(PlayerHype).filter(
    PlayerHype.player_type == 'prospect'
).count()
print(f'Prospects in leaderboard: {prospects}')
db.close()
"
```

## Optional: Clean Up Test Data

Remove the 3 MLB test players (Ohtani, Judge, Skenes) that were created during testing:

```python
# Cleanup script
from app.db.database import SyncSessionLocal
from app.models.hype import PlayerHype, SearchTrend

db = SyncSessionLocal()

# Remove MLB players
mlb_players = db.query(PlayerHype).filter(
    PlayerHype.player_type == 'mlb'
).all()

for player in mlb_players:
    print(f"Removing: {player.player_name}")
    # Delete associated search trends
    db.query(SearchTrend).filter(
        SearchTrend.player_hype_id == player.id
    ).delete()
    db.delete(player)

db.commit()
db.close()
```

## Future: Link PlayerHype to Prospects Table

For better data integrity, consider adding a foreign key:

```python
class PlayerHype(Base):
    # ...existing fields...

    # Optional: Link to prospects table
    prospect_mlb_id = Column(String(10), ForeignKey('prospects.mlb_id'), nullable=True)

    # Relationship
    prospect = relationship("Prospect", foreign_keys=[prospect_mlb_id])
```

This ensures:
- Can only create hype for existing prospects
- Automatic cascade delete
- Better data consistency
- Easy joins for queries

## Summary

**Quick Fix**: Filter `player_type = 'prospect'` in leaderboard endpoint
**Complete Fix**: Add FK relationship to prospects table
**Cleanup**: Remove 3 test MLB players from database
