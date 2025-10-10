"""Compare V4 vs V5 vs V6 rankings."""
import pandas as pd
import numpy as np

print('=' * 100)
print('PROSPECT RANKING VERSIONS COMPARISON')
print('=' * 100)

# Load all versions
v4 = pd.read_csv('prospect_rankings_hitters.csv')
v5 = pd.read_csv('prospect_rankings_v5_hitters_mlb_projected.csv')
v6 = pd.read_csv('prospect_rankings_v6_blended.csv')

print(f'\nV4 (Performance):  {len(v4):,} prospects')
print(f'V5 (Projection):   {len(v5):,} prospects')
print(f'V6 (Blended 70/30): {len(v6):,} prospects')

# Merge all rankings
v4_slim = v4[['mlb_player_id', 'full_name', 'rank']].rename(columns={'rank': 'v4_rank', 'full_name': 'name_v4'})
v5_slim = v5[['mlb_player_id', 'full_name', 'rank']].rename(columns={'rank': 'v5_rank', 'full_name': 'name_v5'})
v6_slim = v6[['mlb_player_id', 'full_name', 'rank']].rename(columns={'rank': 'v6_rank', 'full_name': 'name_v6'})

comparison = v4_slim.merge(v5_slim, on='mlb_player_id', how='outer')
comparison = comparison.merge(v6_slim, on='mlb_player_id', how='outer')
comparison['full_name'] = comparison['name_v4'].fillna(comparison['name_v5']).fillna(comparison['name_v6'])
comparison = comparison[['mlb_player_id', 'full_name', 'v4_rank', 'v5_rank', 'v6_rank']]

# Only players in all 3
all_three = comparison.dropna().copy()
print(f'\nPlayers in all 3 versions: {len(all_three)}')

# Top 50 comparison
print('\n' + '=' * 100)
print('TOP 50 COMPARISON')
print('=' * 100)

v4_top50 = set(v4[v4['rank'] <= 50]['mlb_player_id'])
v5_top50 = set(v5[v5['rank'] <= 50]['mlb_player_id'])
v6_top50 = set(v6[v6['rank'] <= 50]['mlb_player_id'])

print(f'\nV4 vs V5 overlap: {len(v4_top50 & v5_top50)} / 50 ({len(v4_top50 & v5_top50)*2}%)')
print(f'V4 vs V6 overlap: {len(v4_top50 & v6_top50)} / 50 ({len(v4_top50 & v6_top50)*2}%)')
print(f'V5 vs V6 overlap: {len(v5_top50 & v6_top50)} / 50 ({len(v5_top50 & v6_top50)*2}%)')
print(f'All 3 overlap:    {len(v4_top50 & v5_top50 & v6_top50)} / 50 ({len(v4_top50 & v5_top50 & v6_top50)*2}%)')

# Top 10 from each version
print('\n' + '=' * 100)
print('TOP 10 FROM EACH VERSION')
print('=' * 100)

top10_comparison = pd.DataFrame({
    'V4 (Performance)': v4.head(10)['full_name'].values,
    'V5 (Projection)': v5.head(10)['full_name'].values,
    'V6 (Blended 70/30)': v6.head(10)['full_name'].values,
})

print(top10_comparison.to_string(index=True))

# Top 50 table (side by side)
print('\n' + '=' * 100)
print('TOP 50 SIDE-BY-SIDE COMPARISON')
print('=' * 100)

top50_table = pd.DataFrame({
    'Rank': range(1, 51),
    'V4_Name': v4.head(50)['full_name'].values,
    'V5_Name': v5.head(50)['full_name'].values,
    'V6_Name': v6.head(50)['full_name'].values,
})

print(top50_table.to_string(index=False))

# Biggest movers from V4 to V6 (blended impact)
print('\n' + '=' * 100)
print('BIGGEST MOVERS: V4 -> V6')
print('=' * 100)

all_three['v4_to_v6_change'] = all_three['v4_rank'] - all_three['v6_rank']
all_three['abs_change'] = all_three['v4_to_v6_change'].abs()

movers = all_three.sort_values('v4_to_v6_change', ascending=False)

print('\nBiggest Improvements (V6 ranks higher):')
print(movers[['full_name', 'v4_rank', 'v6_rank', 'v4_to_v6_change']].head(20).to_string(index=False))

print('\nBiggest Drops (V6 ranks lower):')
print(movers[['full_name', 'v4_rank', 'v6_rank', 'v4_to_v6_change']].tail(20).to_string(index=False))

# Summary stats
print('\n' + '=' * 100)
print('RANKING CORRELATION ANALYSIS')
print('=' * 100)

# Calculate correlation between versions
corr_v4_v5 = all_three[['v4_rank', 'v5_rank']].corr().iloc[0, 1]
corr_v4_v6 = all_three[['v4_rank', 'v6_rank']].corr().iloc[0, 1]
corr_v5_v6 = all_three[['v5_rank', 'v6_rank']].corr().iloc[0, 1]

print(f'\nSpearman Rank Correlation:')
print(f'  V4 vs V5: {corr_v4_v5:.3f} ({"High" if abs(corr_v4_v5) > 0.7 else "Medium" if abs(corr_v4_v5) > 0.4 else "Low"} agreement)')
print(f'  V4 vs V6: {corr_v4_v6:.3f} ({"High" if abs(corr_v4_v6) > 0.7 else "Medium" if abs(corr_v4_v6) > 0.4 else "Low"} agreement)')
print(f'  V5 vs V6: {corr_v5_v6:.3f} ({"High" if abs(corr_v5_v6) > 0.7 else "Medium" if abs(corr_v5_v6) > 0.4 else "Low"} agreement)')

print(f'\nAverage Rank Changes (V4 baseline):')
print(f'  V4 -> V5: {all_three["v4_rank"].sub(all_three["v5_rank"]).abs().mean():.1f} spots')
print(f'  V4 -> V6: {all_three["v4_rank"].sub(all_three["v6_rank"]).abs().mean():.1f} spots')

# Age analysis
print('\n' + '=' * 100)
print('AGE DISTRIBUTION ANALYSIS')
print('=' * 100)

v4_age = v4.head(50)['current_age'].mean() if 'current_age' in v4.columns else None
v5_age = v5.head(50)['current_age'].mean() if 'current_age' in v5.columns else None
v6_age = v6.head(50)['milb_age'].mean() if 'milb_age' in v6.columns else None

if v4_age:
    print(f'\nAvg Age (Top 50):')
    print(f'  V4: {v4_age:.1f} years')
    if v5_age:
        print(f'  V5: {v5_age:.1f} years')
    if v6_age:
        print(f'  V6: {v6_age:.1f} years')

# Recommendations
print('\n' + '=' * 100)
print('RECOMMENDATIONS')
print('=' * 100)

print('''
USE V4 IF YOU WANT:
- Conservative, proven performance
- Focus on current stats over projection
- Traditional prospect ranking feel
- Less volatility in rankings

USE V5 IF YOU WANT:
- Maximum upside/projection focus
- Aggressive bet on youth
- ML-based MLB outcome prediction
- Dynasty/long-term value

USE V6 IF YOU WANT:
- [*] BALANCED APPROACH (RECOMMENDED)
- Blend of performance + projection (70/30)
- Recency-weighted stats (2025 > 2024 > 2023)
- Focused Statcast (Barrel% only)
- Moderate youth bias (not extreme)
- Best of both worlds

V6 ADVANTAGES:
+ Recency weighting favors current form
+ Only imputes Barrel% (most predictive power metric)
+ 70% performance keeps it grounded
+ 30% projection adds upside consideration
+ Less extreme age bias than V5
+ More stable than V5, more upside-aware than V4
''')

print('=' * 100)
