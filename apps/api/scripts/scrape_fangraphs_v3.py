"""
Scrape FanGraphs 2025 Prospect List - V3
Intercept network requests to find the data API
"""
import asyncio
from playwright.async_api import async_playwright
import json


async def intercept_api_calls(page, url):
    """Monitor network requests to find the data API endpoint."""
    api_calls = []

    async def handle_response(response):
        """Capture API responses."""
        url = response.url
        # Look for API endpoints
        if 'api' in url.lower() or 'json' in response.headers.get('content-type', ''):
            try:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    if 'json' in content_type:
                        data = await response.json()
                        api_calls.append({
                            'url': url,
                            'status': response.status,
                            'data': data
                        })
                        print(f'\n[API FOUND] {url}')
                        print(f'Status: {response.status}')
                        print(f'Data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}')
                        if isinstance(data, list) and len(data) > 0:
                            print(f'Array length: {len(data)}')
                            print(f'First item keys: {list(data[0].keys()) if isinstance(data[0], dict) else type(data[0])}')
            except:
                pass

    page.on('response', handle_response)

    print(f'Loading page: {url}')
    print('Monitoring network requests...\n')

    try:
        await page.goto(url, wait_until='networkidle', timeout=90000)
        print(f'\nPage loaded. Found {len(api_calls)} JSON API calls.')
    except Exception as e:
        print(f'\nPage load error (may be OK): {e}')
        print(f'Found {len(api_calls)} JSON API calls so far.')

    # Wait a bit more for lazy-loaded requests
    await page.wait_for_timeout(5000)

    return api_calls


async def main():
    print('=' * 80)
    print('FANGRAPHS API INTERCEPTOR')
    print('=' * 80)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()

        try:
            # Monitor position player page
            print('\n--- POSITION PLAYERS ---')
            hitter_url = 'https://www.fangraphs.com/prospects/the-board/2025-in-season-prospect-list/scouting-position'
            hitter_apis = await intercept_api_calls(page, hitter_url)

            # Monitor pitcher page
            print('\n--- PITCHERS ---')
            pitcher_url = 'https://www.fangraphs.com/prospects/the-board/2025-in-season-prospect-list/scouting-pitching'
            pitcher_apis = await intercept_api_calls(page, pitcher_url)

            # Summary
            print('\n' + '=' * 80)
            print('SUMMARY')
            print('=' * 80)
            print(f'Hitter APIs found: {len(hitter_apis)}')
            print(f'Pitcher APIs found: {len(pitcher_apis)}')

            # Save API calls to file for inspection
            all_apis = {
                'hitters': hitter_apis,
                'pitchers': pitcher_apis
            }

            with open('fangraphs_api_calls.json', 'w') as f:
                # Serialize just the URLs and first few items
                output = {
                    'hitters': [
                        {
                            'url': call['url'],
                            'data_sample': str(call['data'])[:500] if 'data' in call else None
                        }
                        for call in hitter_apis
                    ],
                    'pitchers': [
                        {
                            'url': call['url'],
                            'data_sample': str(call['data'])[:500] if 'data' in call else None
                        }
                        for call in pitcher_apis
                    ]
                }
                json.dump(output, f, indent=2)

            print('\nAPI calls saved to fangraphs_api_calls.json')

            # If we found prospect data, print sample
            for apis, ptype in [(hitter_apis, 'hitters'), (pitcher_apis, 'pitchers')]:
                for api in apis:
                    data = api.get('data')
                    if isinstance(data, list) and len(data) > 10:
                        print(f'\n{ptype.upper()} - Potential prospect data found:')
                        print(f'  URL: {api["url"]}')
                        print(f'  Count: {len(data)} items')
                        if len(data) > 0 and isinstance(data[0], dict):
                            print(f'  Sample keys: {list(data[0].keys())}')
                            print(f'  Sample item: {data[0]}')

        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
