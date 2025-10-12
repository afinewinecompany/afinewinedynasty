"""
Scrape FanGraphs 2025 Prospect List - V2
Uses cell-based extraction instead of attributes
"""
import asyncio
from playwright.async_api import async_playwright
from sqlalchemy import text
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine


async def scrape_prospects_from_table(page, url, player_type='hitter'):
    """Scrape prospect data from table cells."""
    print(f'\nScraping {player_type}s from {url}')

    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=90000)
        print('Page loaded, waiting for table...')

        # Wait for table to appear - try multiple selectors
        try:
            await page.wait_for_selector('table tbody tr', timeout=30000)
            print('Table found!')
        except:
            print('Primary selector failed, trying alternative...')
            await page.wait_for_selector('table', timeout=30000)

        # Additional wait for React to fully populate
        await page.wait_for_timeout(3000)

        # Extract data from table cells
        prospects = await page.evaluate('''(playerType) => {
            // Find the main prospect table (usually the largest table)
            const tables = Array.from(document.querySelectorAll('table'));
            let prospectTable = tables.find(t => t.querySelectorAll('tbody tr').length > 50);

            if (!prospectTable && tables.length > 0) {
                prospectTable = tables[0];
            }

            if (!prospectTable) {
                return { error: 'No table found', tableCount: tables.length };
            }

            const rows = Array.from(prospectTable.querySelectorAll('tbody tr'));
            console.log(`Found ${rows.length} rows in table`);

            return rows.map((row, idx) => {
                const cells = Array.from(row.querySelectorAll('td'));

                if (cells.length === 0) {
                    return null;  // Skip header rows
                }

                // Extract text from cells
                const cellTexts = cells.map(cell => cell.textContent.trim());

                // Try to get player ID from any data attributes or links
                let playerId = row.getAttribute('data-player-id') ||
                              row.getAttribute('playerid') ||
                              row.id;

                // Check for links to player pages
                const playerLink = row.querySelector('a[href*="player"]');
                if (playerLink && !playerId) {
                    const href = playerLink.getAttribute('href');
                    const match = href.match(/player[/-]([0-9]+)/i);
                    if (match) playerId = match[1];
                }

                // For hitters, typical column order:
                // Rank, Name, Pos, Org, Top100, Age, Hit, GamePwr, RawPwr, Spd, Fld, FV
                // For pitchers:
                // Rank, Name, Pos, Org, Top100, Age, FB, CB, SL, CH, Cmd, FV

                if (cellTexts.length < 8) {
                    return null;  // Not enough data
                }

                let result = {
                    row_index: idx,
                    player_id: playerId,
                    cell_count: cells.length,
                    cells: cellTexts,
                };

                // Try to parse common positions
                // Usually: Rank(0), Name(1), Pos(2), Org(3), Age(4-5)
                if (cellTexts.length >= 6) {
                    result.ovr_rank = cellTexts[0];
                    result.player_name = cellTexts[1];
                    result.position = cellTexts[2];
                    result.org = cellTexts[3];

                    // Age is usually before the tool grades
                    for (let i = 4; i < Math.min(7, cellTexts.length); i++) {
                        if (cellTexts[i].match(/^[0-9]{2}/)) {
                            result.age = cellTexts[i];
                            break;
                        }
                    }
                }

                return result;
            }).filter(r => r !== null);
        }''', player_type)

        if 'error' in prospects:
            print(f"ERROR: {prospects['error']}")
            print(f"Tables found: {prospects.get('tableCount', 0)}")
            await page.screenshot(path=f'fangraphs_{player_type}_debug.png')
            return []

        print(f'Extracted {len(prospects)} {player_type} rows')

        # Show sample
        if len(prospects) > 0:
            sample = prospects[0]
            print(f'\nSample row:')
            print(f'  Player: {sample.get("player_name", "N/A")}')
            print(f'  Rank: {sample.get("ovr_rank", "N/A")}')
            print(f'  Position: {sample.get("position", "N/A")}')
            print(f'  Org: {sample.get("org", "N/A")}')
            print(f'  Age: {sample.get("age", "N/A")}')
            print(f'  Cell count: {sample.get("cell_count")}')
            print(f'  Cells: {sample.get("cells", [])}')

        return prospects

    except Exception as e:
        print(f'ERROR: {e}')
        await page.screenshot(path=f'fangraphs_{player_type}_error.png')
        raise


async def parse_hitter_row(row_data):
    """Parse hitter row data into structured format."""
    cells = row_data.get('cells', [])

    if len(cells) < 10:
        return None

    # Typical column order (may vary):
    # 0: Rank, 1: Name, 2: Pos, 3: Org, 4: Top100, 5: Age,
    # 6+: Tool grades (Hit, GamePwr, RawPwr, Spd, Fld), Last: FV

    return {
        'fg_player_id': row_data.get('player_id'),
        'player_name': row_data.get('player_name'),
        'ovr_rank': row_data.get('ovr_rank'),
        'position': row_data.get('position'),
        'org': row_data.get('org'),
        'age': row_data.get('age'),
        # Extract tool grades from cells (need to identify which columns)
        'raw_cells': cells,
        'player_type': 'hitter'
    }


async def parse_pitcher_row(row_data):
    """Parse pitcher row data into structured format."""
    cells = row_data.get('cells', [])

    if len(cells) < 10:
        return None

    return {
        'fg_player_id': row_data.get('player_id'),
        'player_name': row_data.get('player_name'),
        'ovr_rank': row_data.get('ovr_rank'),
        'position': row_data.get('position', 'P'),
        'org': row_data.get('org'),
        'age': row_data.get('age'),
        'raw_cells': cells,
        'player_type': 'pitcher'
    }


async def save_to_database(hitters, pitchers):
    """Save scraped data to database."""
    async with engine.begin() as conn:
        # Create table if needed
        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS fangraphs_prospect_grades_raw (
                id SERIAL PRIMARY KEY,
                fg_player_id VARCHAR(50),
                player_name VARCHAR(255),

                -- Rankings
                fg_overall_rank INTEGER,

                -- Basic Info
                position VARCHAR(50),
                organization VARCHAR(100),
                age FLOAT,

                -- Raw cells for manual inspection
                raw_cells JSONB,

                -- Metadata
                player_type VARCHAR(20),
                report_date DATE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        '''))

        print('Database table ready')

        # Insert hitters
        for hitter in hitters:
            if not hitter:
                continue

            await conn.execute(text('''
                INSERT INTO fangraphs_prospect_grades_raw
                (fg_player_id, player_name, fg_overall_rank,
                 position, organization, age, raw_cells, player_type, report_date)
                VALUES
                (:fg_player_id, :player_name, :ovr_rank,
                 :position, :org, :age, :raw_cells::jsonb, :player_type, :report_date)
            '''), {
                **hitter,
                'raw_cells': str(hitter.get('raw_cells', [])),
                'report_date': datetime.now().date()
            })

        print(f'Saved {len(hitters)} hitters')

        # Insert pitchers
        for pitcher in pitchers:
            if not pitcher:
                continue

            await conn.execute(text('''
                INSERT INTO fangraphs_prospect_grades_raw
                (fg_player_id, player_name, fg_overall_rank,
                 position, organization, age, raw_cells, player_type, report_date)
                VALUES
                (:fg_player_id, :player_name, :ovr_rank,
                 :position, :org, :age, :raw_cells::jsonb, :player_type, :report_date)
            '''), {
                **pitcher,
                'raw_cells': str(pitcher.get('raw_cells', [])),
                'report_date': datetime.now().date()
            })

        print(f'Saved {len(pitchers)} pitchers')


async def main():
    print('=' * 80)
    print('FANGRAPHS PROSPECT SCRAPER V2')
    print('=' * 80)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            slow_mo=100
        )

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )

        page = await context.new_page()

        try:
            # Scrape position players
            hitter_url = 'https://www.fangraphs.com/prospects/the-board/2025-in-season-prospect-list/scouting-position'
            hitter_rows = await scrape_prospects_from_table(page, hitter_url, 'hitter')
            hitters = [await parse_hitter_row(row) for row in hitter_rows]
            hitters = [h for h in hitters if h]

            # Scrape pitchers
            pitcher_url = 'https://www.fangraphs.com/prospects/the-board/2025-in-season-prospect-list/scouting-pitching'
            pitcher_rows = await scrape_prospects_from_table(page, pitcher_url, 'pitcher')
            pitchers = [await parse_pitcher_row(row) for row in pitcher_rows]
            pitchers = [p for p in pitchers if p]

            # Save to database
            await save_to_database(hitters, pitchers)

            print('\n' + '=' * 80)
            print('SUMMARY')
            print('=' * 80)
            print(f'Hitters: {len(hitters)}')
            print(f'Pitchers: {len(pitchers)}')
            print(f'Total: {len(hitters) + len(pitchers)}')
            print('=' * 80)

        except Exception as e:
            print(f'ERROR: {e}')
            import traceback
            traceback.print_exc()

        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
