import pandas as pd

df = pd.read_csv('prospect_rankings_v7_fangraphs_integrated.csv')

# Check the problematic players
players = df[df['mlb_player_id'].isin(['800050', '701398', '800724', '800180'])]
players = players.sort_values('rank')

print('Updated V7 Rankings (FV-weighted at 50%):')
print('='*90)
print(players[['rank', 'mlb_player_id', 'name', 'fv', 'fg_score', 'v4_score', 'v5_score', 'v7_score']].to_string(index=False))

print('\n' + '='*90)
print('COMPARISON: Old (70% FG / 20% V4 / 10% V5) vs New (50% FG / 40% V4 / 10% V5)')
print('='*90)

old_df = pd.read_csv('prospect_rankings_v7_fg70_v420_v510.csv')
old_ranks = {}
for _, row in old_df.iterrows():
    old_ranks[row['mlb_player_id']] = row['rank']

for _, row in players.iterrows():
    player_id = row['mlb_player_id']
    old_rank = old_ranks.get(player_id, 'N/A')
    if old_rank != 'N/A':
        change = old_rank - row['rank']
        direction = 'UP' if change > 0 else 'DOWN'
        print(f'{row["name"]:<20} FV:{int(row["fv"]):<3} | Old: #{old_rank:<4} -> New: #{row["rank"]:<4} ({direction} {abs(change)})')
    else:
        print(f'{row["name"]:<20} FV:N/A | Old: N/A -> New: #{row["rank"]:<4}')
