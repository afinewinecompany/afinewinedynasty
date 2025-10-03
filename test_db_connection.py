"""Test database connection and create database if needed."""
import asyncio
import asyncpg
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv('apps/api/.env')

async def test_connection():
    # First try to connect to postgres database (default)
    print("Testing PostgreSQL connection...")
    print(f"Host: {os.getenv('POSTGRES_SERVER', 'localhost')}")
    print(f"Port: {os.getenv('POSTGRES_PORT', '5432')}")
    print(f"User: {os.getenv('POSTGRES_USER', 'postgres')}")
    print(f"Database: {os.getenv('POSTGRES_DB', 'afinewinedynasty')}")

    try:
        # Connect to default postgres database first
        conn = await asyncpg.connect(
            host=os.getenv('POSTGRES_SERVER', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', ''),
            database='postgres'  # Connect to default database first
        )
        print("✅ Successfully connected to PostgreSQL!")

        # Check if our database exists
        db_name = os.getenv('POSTGRES_DB', 'afinewinedynasty')
        result = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )

        if result:
            print(f"✅ Database '{db_name}' exists!")
        else:
            print(f"⚠️  Database '{db_name}' does not exist. Creating it...")
            await conn.execute(f'CREATE DATABASE {db_name}')
            print(f"✅ Database '{db_name}' created successfully!")

        await conn.close()

        # Now test connection to our application database
        print(f"\nTesting connection to '{db_name}' database...")
        app_conn = await asyncpg.connect(
            host=os.getenv('POSTGRES_SERVER', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', ''),
            database=db_name
        )
        print(f"✅ Successfully connected to '{db_name}' database!")

        # Check if migrations have been run
        try:
            tables = await app_conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
            if tables:
                print(f"\n📊 Found {len(tables)} tables:")
                for table in tables[:10]:  # Show first 10 tables
                    print(f"  - {table['tablename']}")
            else:
                print("\n⚠️  No tables found. Migrations need to be run.")
        except Exception as e:
            print(f"\n⚠️  Could not query tables: {e}")

        await app_conn.close()

        print("\n✅ All connection tests passed!")
        print("\nNext step: Run migrations with:")
        print('  cd apps/api')
        print('  "C:\\Users\\lilra\\AppData\\Local\\Programs\\Python\\Python313\\Scripts\\alembic.exe" upgrade head')

    except asyncpg.exceptions.InvalidPasswordError:
        print("❌ ERROR: Invalid password for PostgreSQL user 'postgres'")
        print("\nPlease check:")
        print("1. The password in apps/api/.env file")
        print("2. Your PostgreSQL installation password")
        print("\nYou can reset the password using pgAdmin or psql command line")

    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        print("\nPlease verify:")
        print("1. PostgreSQL service is running")
        print("2. Connection details in apps/api/.env are correct")

if __name__ == "__main__":
    asyncio.run(test_connection())
