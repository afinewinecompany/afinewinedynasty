#!/usr/bin/env python3
"""Import missing 2023 and 2024 data"""

import asyncio
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def import_year(year):
    """Import data for a specific year by modifying and running the 2025 script."""

    print(f"\n{'='*70}")
    print(f"Importing {year} data...")
    print('='*70)

    # Read the 2025 script
    with open('scripts/import_2025_fangraphs_only.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace 2025 with the target year
    content = content.replace('2025', str(year))

    # Write temporary script
    temp_script = f'scripts/import_{year}_temp.py'
    with open(temp_script, 'w', encoding='utf-8') as f:
        f.write(content)

    # Run it
    result = subprocess.run(
        [sys.executable, temp_script],
        capture_output=True,
        text=True
    )

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    # Clean up
    os.remove(temp_script)

    return result.returncode == 0


async def main():
    print("Importing missing FanGraphs years (2023, 2024)...")

    # Import 2023
    success_2023 = await import_year(2023)

    # Import 2024
    success_2024 = await import_year(2024)

    if success_2023 and success_2024:
        print("\n" + "="*70)
        print("ALL YEARS IMPORTED SUCCESSFULLY!")
        print("="*70)
    else:
        print("\nSome imports may have failed. Check output above.")


if __name__ == "__main__":
    asyncio.run(main())
