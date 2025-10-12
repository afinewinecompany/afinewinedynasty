"""
Test Railway database connection
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env file
load_dotenv()

# Check what's loaded
print("=" * 70)
print("TESTING RAILWAY DATABASE CONNECTION")
print("=" * 70)
print()

print("Environment variables check:")
print(f"  DATABASE_URL: {'SET' if os.getenv('DATABASE_URL') else 'NOT SET'}")
print(f"  SQLALCHEMY_DATABASE_URI: {'SET' if os.getenv('SQLALCHEMY_DATABASE_URI') else 'NOT SET'}")
print(f"  POSTGRES_SERVER: {os.getenv('POSTGRES_SERVER', 'NOT SET')}")
print(f"  POSTGRES_USER: {os.getenv('POSTGRES_USER', 'NOT SET')}")
print(f"  POSTGRES_PASSWORD: {'SET' if os.getenv('POSTGRES_PASSWORD') else 'NOT SET'}")
print()

# Try to connect
try:
    from sqlalchemy import create_engine, text

    # Try different connection string options
    db_url = None

    if os.getenv('DATABASE_URL'):
        db_url = os.getenv('DATABASE_URL')
        print(f"Using DATABASE_URL from environment")
    elif os.getenv('SQLALCHEMY_DATABASE_URI'):
        db_url = os.getenv('SQLALCHEMY_DATABASE_URI')
        # Convert async URL to sync URL for testing
        if 'postgresql+asyncpg://' in db_url:
            db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
            print(f"Using SQLALCHEMY_DATABASE_URI (converted to sync)")
        else:
            print(f"Using SQLALCHEMY_DATABASE_URI from environment")
    else:
        print("ERROR: No database URL found in environment variables")
        sys.exit(1)

    # Create engine
    print(f"Attempting connection to database...")
    print(f"Connection string starts with: {db_url[:30]}...")

    engine = create_engine(db_url)

    # Test connection
    with engine.connect() as conn:
        result = conn.execute(text("SELECT current_database(), version()"))
        row = result.fetchone()
        print()
        print("CONNECTION SUCCESSFUL!")
        print(f"  Database: {row[0]}")
        print(f"  Version: {row[1][:50]}...")

        # Check some tables
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
            LIMIT 10
        """))

        print()
        print("Sample tables in database:")
        for row in result:
            print(f"  - {row[0]}")

        # Check play-by-play data
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total_records,
                COUNT(DISTINCT game_id) as unique_games,
                MIN(created_at) as oldest,
                MAX(created_at) as newest
            FROM play_by_play_data
        """))

        row = result.fetchone()
        print()
        print("Play-by-play data status:")
        print(f"  Total records: {row[0]:,}")
        print(f"  Unique games: {row[1]:,}")
        if row[2] and row[3]:
            print(f"  Date range: {row[2].date()} to {row[3].date()}")

except Exception as e:
    print()
    print("CONNECTION FAILED!")
    print(f"Error: {e}")
    print()
    print("Troubleshooting tips:")
    print("1. Check if .env file exists in apps/api directory")
    print("2. Ensure DATABASE_URL or SQLALCHEMY_DATABASE_URI is set")
    print("3. Verify the database credentials are correct")
    print("4. Check if Railway database is running")