#!/usr/bin/env python
"""
Runner script for 2025 MiLB play-by-play data collection.
Provides options for different collection modes.
"""

import sys
import subprocess
from pathlib import Path

def main():
    print("\n" + "="*80)
    print("2025 MiLB Play-by-Play Data Collection Runner")
    print("="*80)
    print("\nThis script collects detailed play-by-play data for the 2025 season,")
    print("including plate appearances and Statcast metrics (when available).")
    print("\nCurrent collection options:")
    print("  1. Test run (3 players) - ~5 minutes")
    print("  2. Small batch (25 players) - ~30 minutes")
    print("  3. Medium batch (100 players) - ~2 hours")
    print("  4. Large batch (500 players) - ~10 hours")
    print("  5. Full collection (all ~4,800 players) - ~2-3 days")
    print("  6. Resume from specific offset")
    print("\n  0. Exit")

    choice = input("\nSelect an option (0-6): ").strip()

    if choice == "0":
        print("Exiting...")
        return

    script_path = Path(__file__).parent / "collect_pbp_2025.py"

    if choice == "1":
        print("\n>>> Running test collection (3 players)...")
        subprocess.run([sys.executable, str(script_path), "--limit", "3"])

    elif choice == "2":
        print("\n>>> Running small batch (25 players)...")
        subprocess.run([sys.executable, str(script_path), "--limit", "25"])

    elif choice == "3":
        print("\n>>> Running medium batch (100 players)...")
        subprocess.run([sys.executable, str(script_path), "--limit", "100"])

    elif choice == "4":
        print("\n>>> Running large batch (500 players)...")
        response = input("This will take ~10 hours. Continue? (yes/no): ").strip()
        if response.lower() == 'yes':
            subprocess.run([sys.executable, str(script_path), "--limit", "500"])
        else:
            print("Cancelled.")

    elif choice == "5":
        print("\n>>> Full collection (all players)")
        print("WARNING: This will take 2-3 days to complete!")
        response = input("Are you sure you want to continue? (yes/no): ").strip()
        if response.lower() == 'yes':
            subprocess.run([sys.executable, str(script_path), "--limit", "10000"])
        else:
            print("Cancelled.")

    elif choice == "6":
        offset = input("Enter offset (number of players to skip): ").strip()
        limit = input("Enter limit (number of players to process): ").strip()

        try:
            offset = int(offset)
            limit = int(limit)
            print(f"\n>>> Running collection with offset={offset}, limit={limit}...")
            subprocess.run([sys.executable, str(script_path),
                          "--offset", str(offset), "--limit", str(limit)])
        except ValueError:
            print("Invalid input. Please enter numbers only.")

    else:
        print("Invalid option. Please select 0-6.")
        return main()

    print("\n" + "="*80)
    print("Collection runner finished!")
    print("="*80)


if __name__ == "__main__":
    main()