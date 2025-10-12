"""Direct HYPE recalculation without model imports"""
import os
import sys
import io

# Set UTF-8 encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from datetime import datetime

load_dotenv()

# Get database URL
DATABASE_URL = os.getenv('SQLALCHEMY_DATABASE_URI', '').replace('postgresql+asyncpg://', 'postgresql://')

print(f"\n{'='*80}")
print("Triggering HYPE Recalculation via SQL UPDATE")
print('='*80)

try:
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Force last_calculated to be old so scheduler picks them up
        result = conn.execute(text("""
            UPDATE player_hype
            SET last_calculated = last_calculated - interval '2 hours'
            WHERE player_name IN ('Michael Arroyo', 'Eli Willits')
            RETURNING player_id, player_name, last_calculated
        """))
        conn.commit()

        updated = result.fetchall()

        print(f"\n✓ Updated {len(updated)} players to force recalculation:")
        for row in updated:
            print(f"  - {row[1]} ({row[0]}): last_calculated set to {row[2]}")

        print(f"\n{'='*80}")
        print("Next Steps:")
        print('='*80)
        print("The HYPE scheduler runs every 15 minutes and will automatically")
        print("recalculate scores for these players on the next run.")
        print(f"\nAlternatively, restart the API server to pick up the new code changes")
        print("and the scheduler will run immediately.")

        print(f"\n✓ Done! Check back in 15 minutes or restart the API server.")

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
