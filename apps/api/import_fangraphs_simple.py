"""
Simple FanGraphs Data Import
No ON CONFLICT, just regular INSERTs
"""
import asyncio
import asyncpg
import csv

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
HITTERS_CSV = r"C:\Users\lilra\Downloads\fangraphs-the-board-hitters-2025.csv"
PITCHERS_CSV = r"C:\Users\lilra\Downloads\fangraphs-the-board-pitchers-2025.csv"

async def import_data():
    conn = await asyncpg.connect(DATABASE_URL)

    # Clear existing data
    await conn.execute("TRUNCATE fangraphs_hitter_grades, fangraphs_pitcher_grades CASCADE")
    print("[OK] Cleared existing data")

    # Import hitters
    with open(HITTERS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            try:
                await conn.execute("""
                    INSERT INTO fangraphs_hitter_grades (
                        fangraphs_player_id, name, position, organization,
                        top_100_rank, fv, hit, power, speed, field, data_year
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                    row['playerid'], row['Name'], row['POS'], row['Org'][:3] if row['Org'] else None,
                    int(row['Rank']) if row['Rank'] else None,
                    int(row['FV']) if row['FV'] else None,
                    int(row['Hit']) if row['Hit'] else None,
                    int(row['Power']) if row['Power'] else None,
                    int(row['Speed']) if row['Speed'] else None,
                    int(row['Field']) if row['Field'] else None,
                    2025
                )
                count += 1
            except Exception as e:
                print(f"[SKIP] {row['Name']}: {e}")

        print(f"[OK] Imported {count} hitters")

    # Import pitchers
    with open(PITCHERS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            try:
                await conn.execute("""
                    INSERT INTO fangraphs_pitcher_grades (
                        fangraphs_player_id, name, position, organization,
                        top_100_rank, fv, fastball, slider, curve, change, command, data_year
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                    row['playerid'], row['Name'], row['POS'], row['Org'][:3] if row['Org'] else None,
                    int(row['Rank']) if row['Rank'] else None,
                    int(row['FV']) if row['FV'] else None,
                    int(row['FB']) if row['FB'] else None,
                    int(row['SL']) if row['SL'] else None,
                    int(row['CB']) if row['CB'] else None,
                    int(row['CH']) if row['CH'] else None,
                    int(row['CMD']) if row['CMD'] else None,
                    2025
                )
                count += 1
            except Exception as e:
                print(f"[SKIP] {row['Name']}: {e}")

        print(f"[OK] Imported {count} pitchers")

    await conn.close()
    print("[OK] Import complete!")

if __name__ == "__main__":
    asyncio.run(import_data())
