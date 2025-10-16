"""Quick check of available ML training data"""
import asyncio
from sqlalchemy import text
from app.db.database import engine


async def check_data():
    async with engine.begin() as conn:
        # Check MiLB game logs
        result = await conn.execute(text("""
            SELECT
                COUNT(*) as total_rows,
                COUNT(DISTINCT mlb_player_id) as unique_players,
                MIN(season) as first_season,
                MAX(season) as last_season,
                SUM(CASE WHEN plate_appearances > 0 THEN 1 ELSE 0 END) as hitter_rows,
                SUM(CASE WHEN innings_pitched > 0 THEN 1 ELSE 0 END) as pitcher_rows
            FROM milb_game_logs
        """))
        milb_stats = result.fetchone()

        # Check MLB game logs
        result = await conn.execute(text("""
            SELECT
                COUNT(*) as total_rows,
                COUNT(DISTINCT mlb_player_id) as unique_players,
                MIN(season) as first_season,
                MAX(season) as last_season
            FROM mlb_game_logs
        """))
        mlb_stats = result.fetchone()

        # Check FanGraphs grades
        result = await conn.execute(text("""
            SELECT
                COUNT(*) as total_rows,
                COUNT(DISTINCT fg_player_id) as unique_players,
                MIN(report_year) as first_year,
                MAX(report_year) as last_year,
                SUM(CASE WHEN hit_future IS NOT NULL THEN 1 ELSE 0 END) as hitters,
                SUM(CASE WHEN fb_future IS NOT NULL THEN 1 ELSE 0 END) as pitchers
            FROM fangraphs_prospect_grades
        """))
        fg_stats = result.fetchone()

        # Check prospects with linkage
        result = await conn.execute(text("""
            SELECT
                COUNT(*) as total_prospects,
                COUNT(fg_player_id) as with_fg_id,
                COUNT(mlb_player_id) as with_mlb_id,
                COUNT(CASE WHEN fg_player_id IS NOT NULL AND mlb_player_id IS NOT NULL THEN 1 END) as with_both
            FROM prospects
        """))
        prospect_stats = result.fetchone()

    print("=" * 80)
    print("ML TRAINING DATA AVAILABILITY")
    print("=" * 80)

    print("\n📊 MiLB Game Logs:")
    print(f"  Total rows: {milb_stats[0]:,}")
    print(f"  Unique players: {milb_stats[1]:,}")
    print(f"  Seasons: {milb_stats[2]}-{milb_stats[3]}")
    print(f"  Hitter games: {milb_stats[4]:,}")
    print(f"  Pitcher games: {milb_stats[5]:,}")

    print("\n⚾ MLB Game Logs:")
    print(f"  Total rows: {mlb_stats[0]:,}")
    print(f"  Unique players: {mlb_stats[1]:,}")
    print(f"  Seasons: {mlb_stats[2]}-{mlb_stats[3]}")

    print("\n📈 FanGraphs Prospect Grades:")
    print(f"  Total rows: {fg_stats[0]:,}")
    print(f"  Unique players: {fg_stats[1]:,}")
    print(f"  Years: {fg_stats[2]}-{fg_stats[3]}")
    print(f"  Hitters: {fg_stats[4]:,}")
    print(f"  Pitchers: {fg_stats[5]:,}")

    print("\n🔗 Prospects Table Linkage:")
    print(f"  Total prospects: {prospect_stats[0]:,}")
    print(f"  With FG ID: {prospect_stats[1]:,} ({prospect_stats[1]/prospect_stats[0]*100:.1f}%)")
    print(f"  With MLB ID: {prospect_stats[2]:,} ({prospect_stats[2]/prospect_stats[0]*100:.1f}%)")
    print(f"  With both IDs: {prospect_stats[3]:,} ({prospect_stats[3]/prospect_stats[0]*100:.1f}%)")

    print("\n" + "=" * 80)
    print("DATA QUALITY ASSESSMENT")
    print("=" * 80)

    # Calculate potential training samples
    training_potential = min(prospect_stats[3], mlb_stats[1])
    print(f"\n✅ Estimated training samples: {training_potential:,} prospects with MiLB+MLB+FG data")

    if training_potential >= 500:
        print("   Status: EXCELLENT - Sufficient data for robust ML models")
    elif training_potential >= 200:
        print("   Status: GOOD - Adequate data for ML models")
    elif training_potential >= 100:
        print("   Status: FAIR - Limited data, expect lower accuracy")
    else:
        print("   Status: POOR - Insufficient data for reliable models")

if __name__ == "__main__":
    asyncio.run(check_data())
