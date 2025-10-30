"""
Test Contact Quality Score implementation

This calculates a comprehensive contact quality score (0-100) based on:
- Pull hard fly balls (ultimate power)
- All hard fly balls
- Hard line drives (quality contact)
- Line drives (consistency)
- Negative adjustments for hard GBs, pop ups, soft contact
"""
import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def calculate_contact_quality_score(metrics):
    """
    Calculate Contact Quality Score (0-100) from batted ball metrics.

    Formula:
        Elite Power (40 pts):
            - Pull Hard FB%: 2.5x multiplier (10% = 25 pts)
            - All Hard FB%: 1.5x multiplier (10% = 15 pts)

        Quality Contact (30 pts):
            - Hard LD%: 2.0x multiplier (10% = 20 pts)
            - All LD%: 0.33x multiplier (30% = 10 pts)

        Negative Adjustments (-30 pts):
            - Hard GB%: -1.0x (10% = -10 pts)
            - Pop Up%: -1.0x (10% = -10 pts)
            - Soft%: -1.0x (10% = -10 pts)

        Baseline (30 pts):
            - Hard Hit%: 1.5x (10% = 15 pts)
            - FB%: 0.33x (30% = 10 pts)
            - LD%: 0.17x (30% = 5 pts) [already counted]
    """
    score = 0.0

    # Elite Power (40 points)
    pull_hard_fb = metrics.get('pull_hard_fb_rate', 0)
    hard_fb = metrics.get('hard_fb_rate', 0)
    score += pull_hard_fb * 2.5  # 10% = 25 pts
    score += hard_fb * 1.5        # 10% = 15 pts

    # Quality Contact (30 points)
    hard_ld = metrics.get('hard_ld_rate', 0)
    all_ld = metrics.get('line_drive_rate', 0)
    score += hard_ld * 2.0        # 10% = 20 pts
    score += all_ld * 0.33        # 30% = 10 pts

    # Negative Adjustments (-30 points possible)
    hard_gb = metrics.get('hard_gb_rate', 0)
    popup = metrics.get('popup_rate', 0)
    soft = metrics.get('soft_hit_rate', 0)
    score -= hard_gb * 1.0        # 10% = -10 pts
    score -= popup * 1.0           # 10% = -10 pts
    score -= soft * 1.0            # 10% = -10 pts

    # Baseline Ability (30 points)
    hard_hit = metrics.get('hard_hit_rate', 0)
    all_fb = metrics.get('fly_ball_rate', 0)
    score += hard_hit * 1.5       # 10% = 15 pts
    score += all_fb * 0.33        # 30% = 10 pts

    # Cap between 0-100
    return max(0, min(100, score))

def get_contact_quality_breakdown(player_name, mlb_id):
    """Get comprehensive contact quality breakdown for a player."""
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    cursor.execute("""
        WITH player_batted_balls AS (
            SELECT
                trajectory,
                hardness,
                CASE
                    WHEN hit_location IN (7, 78) THEN 'Pull'
                    WHEN hit_location IN (8, 5) THEN 'Center'
                    WHEN hit_location IN (9, 89) THEN 'Oppo'
                END as direction
            FROM milb_batter_pitches
            WHERE mlb_batter_id = %s
                AND season = 2025
                AND contact = TRUE
                AND foul = FALSE
                AND trajectory IS NOT NULL
                AND hardness IS NOT NULL
        )
        SELECT
            COUNT(*) as total_bip,

            -- Pull hard fly balls (ultimate power)
            COUNT(*) FILTER (WHERE trajectory = 'fly_ball' AND hardness = 'hard' AND direction = 'Pull') * 100.0 /
                NULLIF(COUNT(*), 0) as pull_hard_fb_rate,

            -- All hard fly balls
            COUNT(*) FILTER (WHERE trajectory = 'fly_ball' AND hardness = 'hard') * 100.0 /
                NULLIF(COUNT(*), 0) as hard_fb_rate,

            -- Hard line drives
            COUNT(*) FILTER (WHERE trajectory = 'line_drive' AND hardness = 'hard') * 100.0 /
                NULLIF(COUNT(*), 0) as hard_ld_rate,

            -- All line drives
            COUNT(*) FILTER (WHERE trajectory = 'line_drive') * 100.0 /
                NULLIF(COUNT(*), 0) as line_drive_rate,

            -- All fly balls
            COUNT(*) FILTER (WHERE trajectory = 'fly_ball') * 100.0 /
                NULLIF(COUNT(*), 0) as fly_ball_rate,

            -- Hard ground balls (wasted power)
            COUNT(*) FILTER (WHERE trajectory = 'ground_ball' AND hardness = 'hard') * 100.0 /
                NULLIF(COUNT(*), 0) as hard_gb_rate,

            -- Pop ups (bad)
            COUNT(*) FILTER (WHERE trajectory = 'popup') * 100.0 /
                NULLIF(COUNT(*), 0) as popup_rate,

            -- All hard hit
            COUNT(*) FILTER (WHERE hardness = 'hard') * 100.0 /
                NULLIF(COUNT(*), 0) as hard_hit_rate,

            -- Soft contact (weak)
            COUNT(*) FILTER (WHERE hardness = 'soft') * 100.0 /
                NULLIF(COUNT(*), 0) as soft_hit_rate

        FROM player_batted_balls
    """, (mlb_id,))

    row = cursor.fetchone()
    conn.close()

    if not row or row[0] < 50:
        return None

    metrics = {
        'total_bip': row[0],
        'pull_hard_fb_rate': float(row[1]) if row[1] else 0,
        'hard_fb_rate': float(row[2]) if row[2] else 0,
        'hard_ld_rate': float(row[3]) if row[3] else 0,
        'line_drive_rate': float(row[4]) if row[4] else 0,
        'fly_ball_rate': float(row[5]) if row[5] else 0,
        'hard_gb_rate': float(row[6]) if row[6] else 0,
        'popup_rate': float(row[7]) if row[7] else 0,
        'hard_hit_rate': float(row[8]) if row[8] else 0,
        'soft_hit_rate': float(row[9]) if row[9] else 0
    }

    return metrics

if __name__ == "__main__":
    print("=" * 80)
    print("CONTACT QUALITY SCORE TESTING")
    print("=" * 80)

    # Test with known prospects
    test_players = [
        ('Jesús Made', '815908'),
        ('Roman Anthony', '701350'),
        ('Kristian Campbell', '692225')
    ]

    for name, mlb_id in test_players:
        print(f"\n{name} (ID: {mlb_id}):")
        print("-" * 60)

        metrics = get_contact_quality_breakdown(name, mlb_id)

        if not metrics:
            print("  Insufficient data (need 50+ balls in play)")
            continue

        print(f"  Sample: {metrics['total_bip']} balls in play")
        print(f"\n  Elite Power Outcomes:")
        print(f"    Pull Hard Fly Balls: {metrics['pull_hard_fb_rate']:5.1f}%  (× 2.5 = {metrics['pull_hard_fb_rate']*2.5:5.1f} pts)")
        print(f"    All Hard Fly Balls:  {metrics['hard_fb_rate']:5.1f}%  (× 1.5 = {metrics['hard_fb_rate']*1.5:5.1f} pts)")

        print(f"\n  Quality Contact:")
        print(f"    Hard Line Drives:    {metrics['hard_ld_rate']:5.1f}%  (× 2.0 = {metrics['hard_ld_rate']*2.0:5.1f} pts)")
        print(f"    All Line Drives:     {metrics['line_drive_rate']:5.1f}%  (× 0.33 = {metrics['line_drive_rate']*0.33:5.1f} pts)")

        print(f"\n  Negative Adjustments:")
        print(f"    Hard Ground Balls:   {metrics['hard_gb_rate']:5.1f}%  (× -1.0 = {metrics['hard_gb_rate']*-1.0:5.1f} pts)")
        print(f"    Pop Ups:             {metrics['popup_rate']:5.1f}%  (× -1.0 = {metrics['popup_rate']*-1.0:5.1f} pts)")
        print(f"    Soft Contact:        {metrics['soft_hit_rate']:5.1f}%  (× -1.0 = {metrics['soft_hit_rate']*-1.0:5.1f} pts)")

        print(f"\n  Baseline Ability:")
        print(f"    Hard Hit Rate:       {metrics['hard_hit_rate']:5.1f}%  (× 1.5 = {metrics['hard_hit_rate']*1.5:5.1f} pts)")
        print(f"    Fly Ball Rate:       {metrics['fly_ball_rate']:5.1f}%  (× 0.33 = {metrics['fly_ball_rate']*0.33:5.1f} pts)")

        # Calculate score
        score = calculate_contact_quality_score(metrics)

        print(f"\n  CONTACT QUALITY SCORE: {score:.1f}/100")

        # Interpret score
        if score >= 80:
            interpretation = "Elite Power"
        elif score >= 65:
            interpretation = "Above Average Power"
        elif score >= 50:
            interpretation = "Average Contact"
        elif score >= 35:
            interpretation = "Below Average Contact"
        else:
            interpretation = "Poor Contact Quality"

        print(f"  Interpretation: {interpretation}")

    print("\n" + "=" * 80)
    print("SCORE INTERPRETATION GUIDE")
    print("=" * 80)
    print("\n  80-100: Elite Power (High HR potential, pull-side power)")
    print("  65-79:  Above Average Power (Good power, quality contact)")
    print("  50-64:  Average Contact (Solid contact, moderate power)")
    print("  35-49:  Below Average Contact (Limited power)")
    print("  0-34:   Poor Contact Quality (Weak contact)")

    print("\n  The Contact Quality Score combines:")
    print("  - Pull hard fly balls (ultimate power indicator)")
    print("  - Overall hard contact rate")
    print("  - Line drive production")
    print("  - Penalizes wasted power (hard GBs), weak outcomes (PUs, soft contact)")
