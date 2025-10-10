"""
Import FanGraphs 2025 Prospects from CSV files
Clears existing prospects and reimports from The Board hitters and pitchers CSVs
"""

import csv
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import SyncSessionLocal
from app.db.models import Prospect
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def normalize_position(position: str) -> str:
    """
    Normalize non-standard positions to valid database values.
    Maps various pitcher types and specialty positions to standard codes.
    """
    position = position.strip().upper()

    # Pitcher position mappings
    position_map = {
        'MIRP': 'RP',   # Middle reliever pitcher
        'LRP': 'RP',    # Long reliever pitcher
        'SRP': 'RP',    # Setup reliever pitcher
        'CL': 'RP',     # Closer
        'LHRP': 'RP',   # Left-handed reliever pitcher
        'RHRP': 'RP',   # Right-handed reliever pitcher
        'LOOGY': 'RP',  # Left-handed one-out guy
        'SWINGMAN': 'SP',  # Swing man (can start or relieve)
        'SIRP': 'RP',   # Short-inning reliever pitcher
        'TWP': 'RP',    # Two-way player (pitcher) -> RP for simplicity

        # Position player mappings
        'OF': 'CF',     # Generic outfielder -> Center field
        'IF': '2B',     # Generic infielder -> Second base
        'UT': 'DH',     # Utility player -> DH
        'UTIL': 'DH',   # Utility -> DH
    }

    normalized = position_map.get(position, position)

    # Validate against allowed positions
    valid_positions = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH', 'SP', 'RP']
    if normalized not in valid_positions:
        logger.warning(f"Unknown position '{position}' -> defaulting to 'DH'")
        return 'DH'

    if normalized != position:
        logger.debug(f"Normalized position: {position} -> {normalized}")

    return normalized


def clear_prospects_table(db):
    """Clear all prospects from the table (and related data)"""
    try:
        count = db.query(Prospect).count()
        logger.info(f"Found {count} existing prospects in database")

        # Delete related data first to avoid foreign key constraints
        logger.info("Clearing related tables...")

        # Clear scouting grades
        from app.db.models import ScoutingGrades
        grades_count = db.query(ScoutingGrades).delete()
        logger.info(f"  Cleared {grades_count} scouting grades")

        # Clear prospect stats
        from app.db.models import ProspectStats
        stats_count = db.query(ProspectStats).delete()
        logger.info(f"  Cleared {stats_count} prospect stats")

        db.commit()

        # Now delete all prospects
        db.query(Prospect).delete()
        db.commit()

        logger.info(f"✅ Cleared {count} prospects from database")
        return count
    except Exception as e:
        logger.error(f"Error clearing prospects: {e}")
        db.rollback()
        raise


def import_prospects_from_csv(db, csv_file_path, prospect_type):
    """Import prospects from a CSV file"""

    imported_count = 0
    skipped_count = 0

    logger.info(f"\nImporting {prospect_type} from {csv_file_path}")

    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)

            for row in reader:
                try:
                    name = row['Name'].strip()
                    position = row['Pos'].strip()
                    organization = row['Org'].strip()
                    player_id = row['PlayerId'].strip()

                    # Skip if no player ID
                    if not player_id:
                        logger.warning(f"Skipping {name} - no PlayerID")
                        skipped_count += 1
                        continue

                    # Normalize position to valid database value
                    position = normalize_position(position)

                    # Parse age if available
                    age = None
                    try:
                        age_str = row.get('Age', '').strip()
                        if age_str:
                            age = int(float(age_str))
                    except (ValueError, AttributeError):
                        pass

                    # Check if prospect already exists (in case of duplicates)
                    existing = db.query(Prospect).filter(
                        Prospect.mlb_id == player_id
                    ).first()

                    if existing:
                        logger.debug(f"Updating existing prospect: {name}")
                        existing.name = name
                        existing.position = position
                        existing.organization = organization
                        if age:
                            existing.age = age
                    else:
                        # Create new prospect
                        prospect = Prospect(
                            mlb_id=player_id,
                            name=name,
                            position=position,
                            organization=organization,
                            age=age,
                            level=None,  # Not provided in CSV
                            eta_year=2025  # Default for 2025 prospects
                        )
                        db.add(prospect)

                    imported_count += 1

                    # Commit in batches of 50 for better performance
                    if imported_count % 50 == 0:
                        db.commit()
                        logger.info(f"  Imported {imported_count} {prospect_type}...")

                except Exception as e:
                    logger.error(f"Error importing row: {row.get('Name', 'Unknown')} - {e}")
                    skipped_count += 1
                    continue

            # Final commit
            db.commit()

        logger.info(f"✅ Imported {imported_count} {prospect_type}")
        if skipped_count > 0:
            logger.warning(f"⚠️  Skipped {skipped_count} rows due to errors")

        return imported_count, skipped_count

    except FileNotFoundError:
        logger.error(f"❌ File not found: {csv_file_path}")
        raise
    except Exception as e:
        logger.error(f"❌ Error reading CSV: {e}")
        db.rollback()
        raise


def main():
    """Main import process"""

    # CSV file paths
    hitters_csv = r"C:\Users\lilra\Downloads\fangraphs-the-board-hitters-2025.csv"
    pitchers_csv = r"C:\Users\lilra\Downloads\fangraphs-the-board-pitchers-2025.csv"

    # Check if files exist
    if not os.path.exists(hitters_csv):
        logger.error(f"❌ Hitters CSV not found: {hitters_csv}")
        return

    if not os.path.exists(pitchers_csv):
        logger.error(f"❌ Pitchers CSV not found: {pitchers_csv}")
        return

    logger.info("="*60)
    logger.info("FanGraphs 2025 Prospects Import")
    logger.info("="*60)

    db = SyncSessionLocal()

    try:
        # Step 1: Clear existing prospects
        logger.info("\n📋 Step 1: Clearing existing prospects...")
        cleared_count = clear_prospects_table(db)

        # Step 2: Import hitters
        logger.info("\n⚾ Step 2: Importing hitters...")
        hitters_imported, hitters_skipped = import_prospects_from_csv(
            db, hitters_csv, "hitters"
        )

        # Step 3: Import pitchers (will update duplicates from hitters)
        logger.info("\n⚾ Step 3: Importing pitchers...")
        pitchers_imported, pitchers_skipped = import_prospects_from_csv(
            db, pitchers_csv, "pitchers"
        )

        # Step 4: Get final count
        final_count = db.query(Prospect).count()

        # Summary
        logger.info("\n" + "="*60)
        logger.info("📊 Import Summary")
        logger.info("="*60)
        logger.info(f"Prospects cleared: {cleared_count}")
        logger.info(f"Hitters processed: {hitters_imported} (skipped: {hitters_skipped})")
        logger.info(f"Pitchers processed: {pitchers_imported} (skipped: {pitchers_skipped})")
        logger.info(f"Total prospects in database: {final_count}")
        logger.info("="*60)

        # Sample data check
        logger.info("\n🔍 Sample prospects:")
        samples = db.query(Prospect).limit(5).all()
        for p in samples:
            logger.info(f"  - {p.name} ({p.position}) - {p.organization} [ID: {p.mlb_id}]")

        logger.info("\n✅ Import completed successfully!")

    except Exception as e:
        logger.error(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()