# Data Quality & Architecture Fix Action Plan

## Priority 1: Create MLB Game Logs Table (BLOCKING)

### Step 1: Create Migration
```sql
-- Migration 018_add_mlb_game_logs.py
CREATE TABLE mlb_game_logs (
    id INTEGER PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),
    mlb_player_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    game_pk BIGINT NOT NULL,
    game_date DATE NOT NULL,
    -- Mirror structure from milb_game_logs
    -- 36 hitting stats + 63 pitching stats
);

CREATE UNIQUE INDEX ON mlb_game_logs(mlb_player_id, game_pk, season);
```

### Step 2: Run MLB Collection
```bash
python scripts/collect_mlb_gamelogs.py --seasons 2021 2022 2023 2024
```

## Priority 2: Fix Prospect Linkage (CRITICAL)

### Step 1: Create Player Mapping Table
```sql
-- Migration 019_add_player_mapping.py
CREATE TABLE player_mapping (
    id INTEGER PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),
    mlb_player_id INTEGER UNIQUE,
    fangraphs_id VARCHAR(50),
    baseball_reference_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Step 2: Populate Mappings
```python
# scripts/fix_player_mappings.py
async def link_players():
    # 1. Match by name + team
    # 2. Use MLB API person endpoint
    # 3. Manual verification for ambiguous cases
```

### Step 3: Update MiLB Game Logs
```sql
UPDATE milb_game_logs m
SET prospect_id = (
    SELECT pm.prospect_id
    FROM player_mapping pm
    WHERE pm.mlb_player_id = m.mlb_player_id
)
WHERE prospect_id IS NULL;
```

## Priority 3: Data Validation Pipeline

### Step 1: Create Validation Service
```python
# app/services/data_validation_service.py
class DataValidationService:
    async def validate_linkages(self):
        """Check all foreign key relationships"""

    async def validate_completeness(self):
        """Ensure no NULL critical fields"""

    async def validate_consistency(self):
        """Check ID format consistency"""
```

### Step 2: Add Pre-ML Validation
```python
# scripts/train_milb_to_mlb_predictor.py
async def validate_data_quality():
    """Run before training any models"""
    # Check linkage rate > 95%
    # Verify MLB data exists
    # Ensure prospect metadata available
```

## Priority 4: Establish ID Standards

### Naming Convention
- `prospect_id`: Internal primary key (integer)
- `mlb_id`: MLB Stats API ID (string, store as-is)
- `mlb_player_id`: MLB Stats API ID (integer for queries)
- `fangraphs_id`: Fangraphs player ID
- `bbref_id`: Baseball Reference ID

### Conversion Rules
```python
def normalize_mlb_id(mlb_id: str) -> int:
    """Convert string MLB ID to integer"""
    return int(mlb_id.strip())

def format_mlb_id(player_id: int) -> str:
    """Convert integer to string MLB ID"""
    return str(player_id)
```

## Implementation Timeline

### Week 1: Foundation
- [ ] Create MLB game logs migration
- [ ] Create player mapping table
- [ ] Build mapping population script

### Week 2: Data Repair
- [ ] Run player matching algorithm
- [ ] Update NULL prospect_ids
- [ ] Collect missing MLB data

### Week 3: Validation
- [ ] Build validation service
- [ ] Add quality checks to ML pipeline
- [ ] Document ID standards

### Week 4: ML Retraining
- [ ] Re-run feature engineering with complete data
- [ ] Retrain all models with proper linkages
- [ ] Compare performance metrics

## Success Metrics

- **Linkage Rate**: >95% of game logs linked to prospects
- **MLB Coverage**: MLB data for 100% of graduated players
- **ID Consistency**: Zero mismatched IDs between tables
- **ML Performance**: 20-30% improvement in prediction accuracy

## Risk Mitigation

1. **Backup Before Changes**: Full database backup before migrations
2. **Staged Rollout**: Test on dev environment first
3. **Rollback Plan**: Keep migration down() methods updated
4. **Manual Review**: Sample 100 random linkages for accuracy
5. **Monitoring**: Track linkage metrics daily

## Code Examples

### Check Current Linkage Rate
```python
async def check_linkage_rate():
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(prospect_id) as linked,
                ROUND(COUNT(prospect_id)::numeric / COUNT(*) * 100, 2) as linkage_rate
            FROM milb_game_logs
        """))
        return result.fetchone()
```

### Find Unmapped Players
```python
async def find_unmapped_players():
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT DISTINCT
                mlb_player_id,
                COUNT(*) as game_count
            FROM milb_game_logs
            WHERE prospect_id IS NULL
            GROUP BY mlb_player_id
            ORDER BY game_count DESC
            LIMIT 100
        """))
        return result.fetchall()
```

## Next Steps

1. Review this plan with the team
2. Get approval for database schema changes
3. Schedule maintenance window for migrations
4. Begin implementation with Priority 1

---

*Generated by BMad QA Party Mode Analysis*
*Critical Issues Found: 3 | Recommendations: 12 | Estimated Fix Time: 4 weeks*