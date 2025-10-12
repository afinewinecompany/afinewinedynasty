#!/usr/bin/env python
"""
Run MiLB play-by-play collection with Railway database connection.
Focuses on collecting missing data for 2021-2024 seasons.
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Load environment first
load_dotenv()

# Add scripts directory to path
script_dir = Path(__file__).parent / "scripts"
sys.path.insert(0, str(script_dir))

def main():
    print("\n" + "="*80)
    print("MiLB Play-by-Play Data Collection for Railway Database")
    print("="*80)

    # Verify database connection
    db_url = os.getenv('SQLALCHEMY_DATABASE_URI') or os.getenv('DATABASE_URL')
    if not db_url:
        print("ERROR: No database URL found in environment")
        print("Please ensure .env file contains SQLALCHEMY_DATABASE_URI or DATABASE_URL")
        return

    print("\n[OK] Database connection configured")
    print("\nCurrent data status:")
    print("  2025: 217,470 plate appearances (good coverage)")
    print("  2024: 74,550 plate appearances (needs more)")
    print("  2023: 75,818 plate appearances (needs more)")
    print("  2022: 54,295 plate appearances (needs more)")
    print("  2021: 0 plate appearances (needs collection)")

    print("\nCollection options:")
    print("  1. Collect 2021 data only (highest priority)")
    print("  2. Collect 2021-2022 data")
    print("  3. Collect 2021-2024 data (fill all gaps)")
    print("  4. Test run (10 players from 2021)")
    print("  5. Custom collection")
    print("  0. Exit")

    choice = input("\nSelect an option (0-5): ").strip()

    if choice == "0":
        print("Exiting...")
        return

    # Change to scripts directory for collection
    os.chdir(script_dir)

    if choice == "1":
        print("\n>>> Starting 2021 collection...")
        print("This will collect play-by-play data for all players from 2021")
        response = input("Continue? (yes/no): ").strip()
        if response.lower() == 'yes':
            subprocess.run([
                sys.executable,
                "collect_milb_pbp_data.py",
                "--seasons", "2021",
                "--limit", "1000"  # Process in batches
            ])

    elif choice == "2":
        print("\n>>> Starting 2021-2022 collection...")
        response = input("This will take several hours. Continue? (yes/no): ").strip()
        if response.lower() == 'yes':
            subprocess.run([
                sys.executable,
                "collect_milb_pbp_data.py",
                "--seasons", "2021", "2022",
                "--limit", "500"
            ])

    elif choice == "3":
        print("\n>>> Starting 2021-2024 collection...")
        print("WARNING: This will take 1-2 days to complete!")
        response = input("Are you sure? (yes/no): ").strip()
        if response.lower() == 'yes':
            subprocess.run([
                sys.executable,
                "collect_milb_pbp_data.py",
                "--seasons", "2021", "2022", "2023", "2024"
            ])

    elif choice == "4":
        print("\n>>> Running test collection (10 players from 2021)...")
        subprocess.run([
            sys.executable,
            "collect_milb_pbp_data.py",
            "--seasons", "2021",
            "--limit", "10"
        ])

    elif choice == "5":
        seasons = input("Enter seasons (comma-separated, e.g., 2021,2022): ").strip()
        limit = input("Enter player limit (or press Enter for all): ").strip()

        seasons_list = [s.strip() for s in seasons.split(",")]

        cmd = [sys.executable, "collect_milb_pbp_data.py", "--seasons"] + seasons_list
        if limit:
            cmd.extend(["--limit", limit])

        print(f"\n>>> Running custom collection for seasons: {', '.join(seasons_list)}")
        subprocess.run(cmd)

    else:
        print("Invalid option.")
        return main()

    print("\n" + "="*80)
    print("Collection process completed!")
    print("Check the database for new play-by-play data.")
    print("="*80)


if __name__ == "__main__":
    main()