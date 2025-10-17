#!/usr/bin/env python3
"""Fix the remaining pitch collection scripts (2021, 2022, 2023) by copying the corrected process_game method from 2025."""

import re

# Read the 2025 file to get the correct process_game method
with open('collect_pitch_data_2025.py', 'r') as f:
    content_2025 = f.read()

# Extract the process_game method from 2025 (lines 322-415)
# The method starts with "async def process_game" and ends before "async def collect_player_data"
pattern = r'(    async def process_game\(self, db, game_info: Dict, player_id: int\) -> int:.*?)(    async def collect_player_data)'
match = re.search(pattern, content_2025, re.DOTALL)

if not match:
    print("ERROR: Could not find process_game method in 2025 file")
    exit(1)

correct_process_game_method = match.group(1)

# Now fix each of the 2021, 2022, 2023 files
for year in [2021, 2022, 2023]:
    filename = f'collect_pitch_data_{year}.py'
    print(f"Fixing {filename}...")

    with open(filename, 'r') as f:
        content = f.read()

    # Replace SEASON constant in the extracted method
    fixed_method = correct_process_game_method.replace('SEASON = 2025', f'SEASON = {year}')
    fixed_method = fixed_method.replace('season': 2025', f'season': {year}')
    fixed_method = fixed_method.replace(f'SEASON: {year}', 'SEASON')

    # Find and replace the process_game method
    pattern = r'    async def process_game\(self, db, game_info: Dict, player_id: int\) -> int:.*?    async def collect_player_data'
    replacement = fixed_method + '    async def collect_player_data'

    new_content = re.sub(pattern, replacement, content, count=1, flags=re.DOTALL)

    if new_content == content:
        print(f"  WARNING: No changes made to {filename}")
    else:
        with open(filename, 'w') as f:
            f.write(new_content)
        print(f"  ✓ Fixed {filename}")

print("\nAll files fixed!")
