"""
Manually run the hourly collection cycle for ALL players
This simulates what the scheduler does every hour
"""
import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import PlayerHype, SocialMention
from app.services.social_collector import SocialMediaCollector
from app.services.hype_calculator import HypeCalculator

async def run_full_collection():
    """Run collection for all players like the scheduler does"""
    db = SessionLocal()

    try:
        # Get ALL players
        all_players = db.query(PlayerHype).all()
        print(f"Starting collection for {len(all_players)} players")
        print(f"Time: {datetime.utcnow()}")
        print("="*80)

        collector = SocialMediaCollector(db)

        # Track statistics
        success_count = 0
        error_count = 0
        skipped_count = 0
        total_mentions_before = db.query(SocialMention).count()

        # Process in batches like the scheduler
        batch_size = 10
        for i in range(0, len(all_players), batch_size):
            batch = all_players[i:i+batch_size]
            print(f"\nProcessing batch {i//batch_size + 1}/{(len(all_players) + batch_size - 1)//batch_size}")

            tasks = []
            for player in batch:
                tasks.append(
                    collector.collect_all_platforms(
                        player.player_name,
                        player.player_id
                    )
                )

            # Run batch concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for player, result in zip(batch, results):
                if isinstance(result, Exception):
                    print(f"  ❌ {player.player_name}: Error - {result}")
                    error_count += 1
                else:
                    # Check each platform
                    platforms_status = []
                    for platform, data in result.items():
                        status = data.get('status', 'unknown')
                        if status == 'success':
                            count = data.get('count', 0)
                            if count > 0:
                                platforms_status.append(f"{platform}:{count}")
                        elif status == 'skipped':
                            pass  # Don't count skipped as errors
                        else:
                            platforms_status.append(f"{platform}:error")

                    if platforms_status:
                        print(f"  ✓ {player.player_name}: {', '.join(platforms_status)}")
                        success_count += 1
                    else:
                        skipped_count += 1

            # Small delay between batches to be nice to APIs
            await asyncio.sleep(2)

        print("\n" + "="*80)
        print("COLLECTION COMPLETE")
        print("="*80)

        # Get final statistics
        total_mentions_after = db.query(SocialMention).count()
        new_mentions = total_mentions_after - total_mentions_before

        # Count by platform
        from sqlalchemy import func
        platform_counts = db.query(
            SocialMention.platform,
            func.count(SocialMention.id).label('count')
        ).group_by(SocialMention.platform).all()

        print(f"\nResults:")
        print(f"  Players processed: {len(all_players)}")
        print(f"  Successful collections: {success_count}")
        print(f"  Errors: {error_count}")
        print(f"  Skipped (no credentials): {skipped_count}")
        print(f"\nMentions:")
        print(f"  Total before: {total_mentions_before}")
        print(f"  Total after: {total_mentions_after}")
        print(f"  New mentions: {new_mentions}")
        print(f"\nBy Platform:")
        for platform, count in platform_counts:
            print(f"  {platform}: {count} total mentions")

        # Now run HYPE calculations for all players
        print("\n" + "="*80)
        print("CALCULATING HYPE SCORES")
        print("="*80)

        calculator = HypeCalculator(db)
        calc_success = 0
        calc_errors = 0

        for player in all_players:
            try:
                result = calculator.calculate_hype_score(player.player_id)
                calc_success += 1
                if calc_success % 10 == 0:
                    print(f"  Calculated {calc_success}/{len(all_players)}...")
            except Exception as e:
                calc_errors += 1
                print(f"  Error calculating {player.player_name}: {e}")

        print(f"\nHYPE Calculations:")
        print(f"  Success: {calc_success}")
        print(f"  Errors: {calc_errors}")

        # Show top 10 by HYPE score
        print("\n" + "="*80)
        print("TOP 10 BY HYPE SCORE")
        print("="*80)

        top_players = db.query(PlayerHype).order_by(
            PlayerHype.hype_score.desc()
        ).limit(10).all()

        for i, player in enumerate(top_players, 1):
            print(f"{i:2}. {player.player_name:25} | Score: {player.hype_score:6.2f} | 24h: {player.total_mentions_24h:3} | 7d: {player.total_mentions_7d:3} | 14d: {player.total_mentions_14d:3}")

        # Check specifically for Trey Yesavage
        print("\n" + "="*80)
        print("TREY YESAVAGE STATUS")
        print("="*80)

        trey = db.query(PlayerHype).filter(
            PlayerHype.player_name.ilike('%yesavage%')
        ).first()

        if trey:
            print(f"Name: {trey.player_name}")
            print(f"HYPE Score: {trey.hype_score}")
            print(f"24h Mentions: {trey.total_mentions_24h}")
            print(f"7d Mentions: {trey.total_mentions_7d}")
            print(f"14d Mentions: {trey.total_mentions_14d}")

            # Count mentions by platform
            trey_mentions = db.query(
                SocialMention.platform,
                func.count(SocialMention.id).label('count')
            ).filter(
                SocialMention.player_hype_id == trey.id
            ).group_by(SocialMention.platform).all()

            print(f"\nMentions by platform:")
            for platform, count in trey_mentions:
                print(f"  {platform}: {count}")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    print("MANUAL HOURLY COLLECTION CYCLE")
    print("="*80)
    print("This will collect social data for ALL 100 players")
    print("Expected time: 3-5 minutes")
    print("="*80)

    asyncio.run(run_full_collection())