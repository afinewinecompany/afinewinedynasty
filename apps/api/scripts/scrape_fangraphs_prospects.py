"""
Scrape FanGraphs 2025 Prospect List using Playwright.

Sources:
- Position players: https://www.fangraphs.com/prospects/the-board/2025-in-season-prospect-list/scouting-position
- Pitchers: https://www.fangraphs.com/prospects/the-board/2025-in-season-prospect-list/scouting-pitching
"""
import asyncio
from playwright.async_api import async_playwright
from sqlalchemy import text
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine

async def scrape_position_players(page):
    """Scrape position player prospect list."""
    url = 'https://www.fangraphs.com/prospects/the-board/2025-in-season-prospect-list/scouting-position'

    print(f'Scraping position players from {url}')
    # Try with domcontentloaded instead of load - some sites never fire 'load' event
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
    except Exception as e:
        print(f'Failed with domcontentloaded, trying networkidle: {e}')
        await page.goto(url, wait_until='networkidle', timeout=90000)

    # Wait a bit for React to render
    await page.wait_for_timeout(5000)

    # Take a screenshot to see what we got
    await page.screenshot(path='fangraphs_hitters.png')
    print('Screenshot saved to fangraphs_hitters.png')

    # First, let's see what HTML structure we actually have
    html_info = await page.evaluate('''() => {
        const tables = document.querySelectorAll('table');
        const allRows = document.querySelectorAll('tr');
        const rowsWithAttrs = document.querySelectorAll('tr[playerid]');

        // Get first few rows as samples
        const sampleRows = Array.from(allRows).slice(0, 5).map(row => {
            const attrs = Array.from(row.attributes).map(attr => `${attr.name}="${attr.value}"`);
            return {
                html: row.outerHTML.substring(0, 500),
                attributes: attrs,
                cells: row.cells.length
            };
        });

        return {
            tableCount: tables.length,
            totalRows: allRows.length,
            rowsWithPlayerid: rowsWithAttrs.length,
            sampleRows: sampleRows
        };
    }''')

    print('HTML Structure:')
    print(f'  Tables found: {html_info["tableCount"]}')
    print(f'  Total rows: {html_info["totalRows"]}')
    print(f'  Rows with playerid attr: {html_info["rowsWithPlayerid"]}')
    print('\nSample rows:')
    for i, sample in enumerate(html_info["sampleRows"]):
        print(f'\n  Row {i+1}:')
        print(f'    Attributes: {sample["attributes"]}')
        print(f'    Cells: {sample["cells"]}')
        print(f'    HTML: {sample["html"][:200]}...')

    # Try to find table rows - check multiple possible selectors
    prospects = await page.evaluate('''() => {
        // Try different selectors for table rows
        let rows = Array.from(document.querySelectorAll('tr[playerid]'));

        if (rows.length === 0) {
            rows = Array.from(document.querySelectorAll('tbody tr'));
        }

        if (rows.length === 0) {
            rows = Array.from(document.querySelectorAll('table tr'));
        }

        console.log(`Found ${rows.length} rows`);

        return rows.map(row => {
            // Try to get attributes (might be on row or cells)
            const getData = (attr) => row.getAttribute(attr) || '';

            return ({
                player_id: getData('playerid'),
                player_name: getData('playername'),
                position: getData('position'),
                org: getData('org'),
                ovr_rank: getData('ovr_rank'),
                org_rank: getData('org_rank'),
                age: getData('age'),
                fv_current: getData('fv_current'),
                fhit: getData('fhit'),
                fraw: getData('fraw'),
                fspd: getData('fspd'),
                ffld: getData('ffld'),
                farm: getData('farm'),
                phit: getData('phit'),
                praw: getData('praw'),
                pspd: getData('pspd'),
                pfld: getData('pfld'),
                parm: getData('parm'),
                _html: row.outerHTML.substring(0, 200)  // Debug: first 200 chars
            });
        });
    }''')

    print(f'\nFound {len(prospects)} position players')
    if len(prospects) > 0:
        print('\nFirst prospect sample:')
        print(f'  {prospects[0]}')

    return prospects


async def scrape_pitchers(page):
    """Scrape pitcher prospect list."""
    url = 'https://www.fangraphs.com/prospects/the-board/2025-in-season-prospect-list/scouting-pitching'

    print(f'Scraping pitchers from {url}')
    await page.goto(url, wait_until='domcontentloaded', timeout=60000)

    # Wait for table
    await page.wait_for_selector('tr[playerid]', timeout=30000)
    print('Table loaded, extracting data...')

    # Extract pitcher data
    pitchers = await page.evaluate('''() => {
        const rows = Array.from(document.querySelectorAll('tr[playerid]'));
        return rows.map(row => ({
            player_id: row.getAttribute('playerid'),
            player_name: row.getAttribute('playername'),
            position: row.getAttribute('position') || 'P',
            org: row.getAttribute('org'),
            ovr_rank: row.getAttribute('ovr_rank'),
            org_rank: row.getAttribute('org_rank'),
            age: row.getAttribute('age'),
            fv_current: row.getAttribute('fv_current'),
            // Pitcher tool grades (future)
            ffb: row.getAttribute('ffb'),    // Fastball
            fcb: row.getAttribute('fcb'),    // Curveball
            fsl: row.getAttribute('fsl'),    // Slider
            fch: row.getAttribute('fch'),    // Changeup
            fcmd: row.getAttribute('fcmd'),  // Command/Control
            // Present grades
            pfb: row.getAttribute('pfb'),
            pcb: row.getAttribute('pcb'),
            psl: row.getAttribute('psl'),
            pch: row.getAttribute('pch'),
            pcmd: row.getAttribute('pcmd')
        }));
    }''')

    print(f'Found {len(pitchers)} pitchers')
    return pitchers


async def save_to_database(prospects, pitchers):
    """Save scraped data to database."""

    async with engine.begin() as conn:
        # Create table if needed
        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS fangraphs_prospect_grades (
                id SERIAL PRIMARY KEY,
                fg_player_id VARCHAR(50),
                player_name VARCHAR(255),
                mlb_player_id INTEGER,

                -- Rankings
                fg_overall_rank INTEGER,
                fg_org_rank INTEGER,

                -- Basic Info
                position VARCHAR(50),
                organization VARCHAR(100),
                age FLOAT,

                -- Future Value
                future_value INTEGER,  -- 20-80 scale

                -- Hitter Tool Grades (Future)
                hit_tool_future INTEGER,
                power_tool_future INTEGER,
                run_tool_future INTEGER,
                field_tool_future INTEGER,
                arm_tool_future INTEGER,

                -- Hitter Tool Grades (Present)
                hit_tool_present INTEGER,
                power_tool_present INTEGER,
                run_tool_present INTEGER,
                field_tool_present INTEGER,
                arm_tool_present INTEGER,

                -- Pitcher Tool Grades (Future)
                fastball_future INTEGER,
                curveball_future INTEGER,
                slider_future INTEGER,
                changeup_future INTEGER,
                command_future INTEGER,

                -- Pitcher Tool Grades (Present)
                fastball_present INTEGER,
                curveball_present INTEGER,
                slider_present INTEGER,
                changeup_present INTEGER,
                command_present INTEGER,

                -- Metadata
                player_type VARCHAR(20),  -- 'hitter' or 'pitcher'
                report_date DATE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),

                UNIQUE(fg_player_id, report_date)
            )
        '''))

        await conn.execute(text('''
            CREATE INDEX IF NOT EXISTS idx_fg_grades_player_name
            ON fangraphs_prospect_grades(player_name)
        '''))

        print('Database table ready')

        # Insert position players
        for prospect in prospects:
            await conn.execute(text('''
                INSERT INTO fangraphs_prospect_grades
                (fg_player_id, player_name, fg_overall_rank, fg_org_rank,
                 position, organization, age, future_value,
                 hit_tool_future, power_tool_future, run_tool_future, field_tool_future, arm_tool_future,
                 hit_tool_present, power_tool_present, run_tool_present, field_tool_present, arm_tool_present,
                 player_type, report_date)
                VALUES
                (:fg_player_id, :player_name, :ovr_rank, :org_rank,
                 :position, :org, :age, :fv_current,
                 :fhit, :fraw, :fspd, :ffld, :farm,
                 :phit, :praw, :pspd, :pfld, :parm,
                 'hitter', :report_date)
                ON CONFLICT (fg_player_id, report_date) DO UPDATE SET
                    player_name = EXCLUDED.player_name,
                    fg_overall_rank = EXCLUDED.fg_overall_rank,
                    fg_org_rank = EXCLUDED.fg_org_rank,
                    future_value = EXCLUDED.future_value,
                    hit_tool_future = EXCLUDED.hit_tool_future,
                    power_tool_future = EXCLUDED.power_tool_future,
                    run_tool_future = EXCLUDED.run_tool_future,
                    field_tool_future = EXCLUDED.field_tool_future,
                    arm_tool_future = EXCLUDED.arm_tool_future,
                    updated_at = NOW()
            '''), {
                **prospect,
                'report_date': datetime.now().date()
            })

        print(f'Saved {len(prospects)} position players')

        # Insert pitchers
        for pitcher in pitchers:
            await conn.execute(text('''
                INSERT INTO fangraphs_prospect_grades
                (fg_player_id, player_name, fg_overall_rank, fg_org_rank,
                 position, organization, age, future_value,
                 fastball_future, curveball_future, slider_future, changeup_future, command_future,
                 fastball_present, curveball_present, slider_present, changeup_present, command_present,
                 player_type, report_date)
                VALUES
                (:player_id, :player_name, :ovr_rank, :org_rank,
                 :position, :org, :age, :fv_current,
                 :ffb, :fcb, :fsl, :fch, :fcmd,
                 :pfb, :pcb, :psl, :pch, :pcmd,
                 'pitcher', :report_date)
                ON CONFLICT (fg_player_id, report_date) DO UPDATE SET
                    player_name = EXCLUDED.player_name,
                    fg_overall_rank = EXCLUDED.fg_overall_rank,
                    fg_org_rank = EXCLUDED.fg_org_rank,
                    future_value = EXCLUDED.future_value,
                    fastball_future = EXCLUDED.fastball_future,
                    curveball_future = EXCLUDED.curveball_future,
                    slider_future = EXCLUDED.slider_future,
                    changeup_future = EXCLUDED.changeup_future,
                    command_future = EXCLUDED.command_future,
                    updated_at = NOW()
            '''), {
                **pitcher,
                'report_date': datetime.now().date()
            })

        print(f'Saved {len(pitchers)} pitchers')


async def main():
    print('=' * 80)
    print('FANGRAPHS PROSPECT SCRAPER')
    print('=' * 80)

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(
            headless=True,  # Run in background
            slow_mo=100      # Add small delay for stability
        )

        # Create context with user agent
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        page = await context.new_page()

        try:
            # Scrape both lists
            prospects = await scrape_position_players(page)
            pitchers = await scrape_pitchers(page)

            # Save to database
            await save_to_database(prospects, pitchers)

            print('\n' + '=' * 80)
            print('SUMMARY')
            print('=' * 80)
            print(f'Position Players: {len(prospects)}')
            print(f'Pitchers: {len(pitchers)}')
            print(f'Total Prospects: {len(prospects) + len(pitchers)}')
            print('=' * 80)

        except Exception as e:
            print(f'ERROR: {e}')
            # Take screenshot for debugging
            await page.screenshot(path='fangraphs_error.png')
            print('Saved error screenshot to fangraphs_error.png')
            raise

        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
