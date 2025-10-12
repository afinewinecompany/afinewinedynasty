#!/usr/bin/env python
"""
Monitor MiLB play-by-play collection progress
"""
import time
import os
from pathlib import Path

def tail_file(filepath, lines=5):
    """Get last N lines from a file"""
    try:
        with open(filepath, 'r') as f:
            content = f.readlines()
            return ''.join(content[-lines:])
    except FileNotFoundError:
        return "File not found"
    except Exception as e:
        return f"Error: {e}"

def check_collection_status():
    """Check status of all collections"""
    log_dir = Path('logs')

    print("="*80)
    print("MiLB PLAY-BY-PLAY COLLECTION STATUS")
    print("="*80)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    years = [2021, 2022, 2023, 2024]
    batches = ['', '_batch2']

    for year in years:
        print(f"=== {year} Collections ===")

        for batch in batches:
            log_file = log_dir / f"pbp_{year}{batch}.log"

            if not log_file.exists():
                continue

            batch_name = "Batch 1 (100 players)" if batch == '' else "Batch 2 (1000 players)"

            # Get file size
            size_kb = log_file.stat().st_size / 1024
            print(f"  {batch_name}: {size_kb:.1f} KB")

            # Get last few lines
            tail = tail_file(log_file, 2)
            for line in tail.strip().split('\n'):
                if line.strip():
                    # Extract just the message part (after timestamp)
                    parts = line.split(' - INFO - ')
                    if len(parts) > 1:
                        msg = parts[-1][:65]
                        print(f"    {msg}")

        print()

    print("="*80)
    print("Refresh this view by running: python monitor_collections.py")
    print("="*80)

if __name__ == "__main__":
    check_collection_status()
