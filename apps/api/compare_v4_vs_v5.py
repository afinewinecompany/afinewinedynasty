"""Compare v4 (simple translation) vs v5 (ML-projected MLB stats)."""
import pandas as pd

print('COMPARING RANKING APPROACHES')
print('=' * 100)

# Load both rankings
v4 = pd.read_csv('prospect_rankings_hitters.csv')
v5 = pd.read_csv('prospect_rankings_v5_hitters_mlb_projected.csv')

print(f'\nV4 (Simple Translation): {len(v4)} prospects')
print(f'V5 (MLB Projection):     {len(v5)} prospects')

# Merge to compare ranks
v4_slim = v4[['mlb_player_id', 'full_name', 'rank']].rename(columns={'rank': 'v4_rank'})
v5_slim = v5[['mlb_player_id', 'full_name', 'rank']].rename(columns={'rank': 'v5_rank'})

comparison = v4_slim.merge(v5_slim, on='mlb_player_id', how='outer', suffixes=('_v4', '_v5'))
comparison['full_name'] = comparison['full_name_v4'].fillna(comparison['full_name_v5'])
comparison = comparison[['mlb_player_id', 'full_name', 'v4_rank', 'v5_rank']]

# Calculate rank change
comparison['rank_change'] = comparison['v4_rank'] - comparison['v5_rank']
comparison['abs_change'] = comparison['rank_change'].abs()

# Only players in both
both = comparison.dropna().copy()
both = both.sort_values('abs_change', ascending=False)

print('\n' + '=' * 100)
print('BIGGEST MOVERS (Improved in v5 using ML projection)')
print('=' * 100)
print(both.head(20).to_string(index=False))

print('\n' + '=' * 100)
print('BIGGEST FALLERS (Dropped in v5)')
print('=' * 100)
print(both.tail(20).to_string(index=False))

# Top 50 comparison
print('\n' + '=' * 100)
print('TOP 50 COMPARISON')
print('=' * 100)

v4_top50 = set(v4[v4['rank'] <= 50]['mlb_player_id'])
v5_top50 = set(v5[v5['rank'] <= 50]['mlb_player_id'])

only_v4 = v4_top50 - v5_top50
only_v5 = v5_top50 - v4_top50

print(f'\nPlayers in v4 Top 50 but NOT v5: {len(only_v4)}')
if only_v4:
    dropouts = v4[v4['mlb_player_id'].isin(only_v4)][['rank', 'full_name', 'current_age', 'primary_position']]
    print(dropouts.to_string(index=False))

print(f'\nPlayers in v5 Top 50 but NOT v4: {len(only_v5)}')
if only_v5:
    newcomers = v5[v5['mlb_player_id'].isin(only_v5)][['rank', 'full_name', 'current_age', 'primary_position']]
    print(newcomers.to_string(index=False))

print('\n' + '=' * 100)
print('SUMMARY')
print('=' * 100)
print(f'Average absolute rank change: {both["abs_change"].mean():.1f} spots')
print(f'Median absolute rank change:  {both["abs_change"].median():.1f} spots')
print(f'Max rank improvement:         {both["rank_change"].max():.0f} spots')
print(f'Max rank drop:                {both["rank_change"].min():.0f} spots')
