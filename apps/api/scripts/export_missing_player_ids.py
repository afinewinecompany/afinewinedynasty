"""
Export the 23 prospects without MLB player IDs for manual review
"""
import asyncio
import asyncpg
import csv

async def export_missing_ids():
    conn = await asyncpg.connect(
        host="nozomi.proxy.rlwy.net",
        port=39235,
        user="postgres",
        password="BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp",
        database="railway"
    )

    # Get prospects without mlb_player_id
    prospects = await conn.fetch("""
        SELECT
            id,
            name,
            position,
            organization,
            level,
            age,
            eta_year,
            fg_player_id,
            mlb_id,
            ba_player_id,
            created_at
        FROM prospects
        WHERE mlb_player_id IS NULL
        ORDER BY name
    """)

    print(f"Found {len(prospects)} prospects without MLB player ID\n")
    print("=" * 120)
    print(f"{'#':<4} {'Name':<30} {'Pos':<5} {'Org':<25} {'Level':<10} {'FG ID':<15} {'MLB ID':<15} {'BA ID':<15}")
    print("=" * 120)

    for i, p in enumerate(prospects, 1):
        fg_id = p['fg_player_id'] or 'N/A'
        mlb_id = p['mlb_id'] or 'N/A'
        ba_id = p['ba_player_id'] or 'N/A'
        org = p['organization'] or 'N/A'
        level = p['level'] or 'N/A'
        pos = p['position'] or 'N/A'

        print(f"{i:<4} {p['name']:<30} {pos:<5} {org:<25} {level:<10} {fg_id:<15} {mlb_id:<15} {ba_id:<15}")

    # Export to CSV
    with open('prospects_without_mlb_player_id.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Name', 'Position', 'Organization', 'Level', 'Age', 'ETA Year', 'FG Player ID', 'MLB ID', 'BA Player ID', 'Created At'])

        for p in prospects:
            writer.writerow([
                p['id'],
                p['name'],
                p['position'] or '',
                p['organization'] or '',
                p['level'] or '',
                p['age'] or '',
                p['eta_year'] or '',
                p['fg_player_id'] or '',
                p['mlb_id'] or '',
                p['ba_player_id'] or '',
                p['created_at']
            ])

    print("\n" + "=" * 120)
    print(f"Exported to: prospects_without_mlb_player_id.csv")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(export_missing_ids())
