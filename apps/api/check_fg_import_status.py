import asyncio
from sqlalchemy import text
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.db.database import engine

async def main():
    async with engine.begin() as conn:
        result = await conn.execute(text('''
            SELECT report_year, COUNT(*) as cnt
            FROM fangraphs_prospect_grades
            GROUP BY report_year
            ORDER BY report_year
        '''))

        print('Year  | Count')
        print('------|-------')
        for row in result:
            print(f'{row[0]}  | {row[1]:,}')

        result = await conn.execute(text('SELECT COUNT(*) FROM fangraphs_prospect_grades'))
        total = result.scalar()
        print(f'\nTotal: {total:,} prospect-years imported')

        # Expected: ~1,300 per year * 4 years = ~5,200
        expected = 1300 * 4
        pct = (total / expected) * 100 if expected > 0 else 0
        print(f'Expected: ~{expected:,}')
        print(f'Progress: {pct:.1f}%')

if __name__ == '__main__':
    asyncio.run(main())
