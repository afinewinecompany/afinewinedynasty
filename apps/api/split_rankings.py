"""Split unified rankings into separate hitter and pitcher lists."""
import pandas as pd

# Load unified rankings
df = pd.read_csv('prospect_rankings_v3_unified.csv')

# Split by player type
hitters = df[df['player_type'] == 'Hitter'].copy()
pitchers = df[df['player_type'] == 'Pitcher'].copy()

# Renumber ranks
hitters['rank'] = range(1, len(hitters) + 1)
pitchers['rank'] = range(1, len(pitchers) + 1)

# Save
hitters.to_csv('prospect_rankings_hitters.csv', index=False)
pitchers.to_csv('prospect_rankings_pitchers.csv', index=False)

print(f'Hitter Rankings: {len(hitters)} players')
print(f'Pitcher Rankings: {len(pitchers)} players')
print('\nTop 10 Hitters:')
print(hitters[['rank', 'full_name', 'current_age', 'primary_position', 'highest_level', 'prospect_value_score']].head(10).to_string(index=False))
print('\nTop 10 Pitchers:')
print(pitchers[['rank', 'full_name', 'current_age', 'primary_position', 'highest_level', 'prospect_value_score']].head(10).to_string(index=False))
