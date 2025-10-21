"""
Add Priority 3 prospects to database with provided MLB IDs
Handle diacritics and name variations
"""

import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import unicodedata

# Database connection
db_url = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
engine = create_engine(db_url)

# Prospects to add with their MLB IDs (provided manually)
PROSPECTS_TO_ADD = [
    {'name': 'Jesus Made', 'mlb_id': '815908', 'team': 'MIL', 'rank': 3, 'position': 'SS', 'level': 'AA'},
    {'name': 'Luis Pena', 'mlb_id': '650656', 'team': 'MIL', 'rank': 18, 'position': 'SS', 'level': 'A+'},
    {'name': 'Josue Briceno', 'mlb_id': '800522', 'team': 'DET', 'rank': 48, 'position': 'C', 'level': 'AA'},
    {'name': 'Steele Hall', 'mlb_id': '829162', 'team': 'CIN', 'rank': 55, 'position': 'SS', 'level': 'Rookie'},
    {'name': 'JoJo Parker', 'mlb_id': '828098', 'team': 'TOR', 'rank': 56, 'position': 'SS', 'level': 'Rookie'},
    {'name': 'Seth Hernandez', 'mlb_id': '815825', 'team': 'PIT', 'rank': 59, 'position': 'P', 'level': 'Rookie'},
    {'name': 'Josuar Gonzalez', 'mlb_id': '829034', 'team': 'SF', 'rank': 65, 'position': 'SS', 'level': 'Rookie'},
    {'name': 'George Lombard', 'mlb_id': '806146', 'team': 'NYY', 'rank': 68, 'position': 'SS', 'level': 'AA'},
    {'name': 'Moises Ballesteros', 'mlb_id': '694208', 'team': 'CHC', 'rank': 91, 'position': 'C', 'level': 'Majors'},
    {'name': 'Kendry Chourio', 'mlb_id': '830402', 'team': 'KC', 'rank': 92, 'position': 'P', 'level': 'A'}
]

def remove_accents(text):
    """Remove accents from text for matching"""
    if not text:
        return text
    # Normalize to NFD (decomposed form) then filter out accent marks
    nfd = unicodedata.normalize('NFD', text)
    without_accents = ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')
    return without_accents

def check_name_variations(name):
    """Generate possible name variations with and without diacritics"""
    variations = [name]

    # Common Spanish/Latin variations
    replacements = {
        'e': ['é', 'è'],
        'a': ['á', 'à'],
        'i': ['í', 'ì'],
        'o': ['ó', 'ò'],
        'u': ['ú', 'ù', 'ü'],
        'n': ['ñ'],
        'Jose': ['José'],
        'Jesus': ['Jesús'],
        'Luis': ['Luís'],
        'Moises': ['Moisés'],
        'Josue': ['Josué']
    }

    # Generate variations
    for orig, accented_list in replacements.items():
        if orig in name:
            for accented in accented_list:
                variations.append(name.replace(orig, accented))

    # Also add version without accents
    variations.append(remove_accents(name))

    return list(set(variations))

def add_prospects_to_database():
    """Add the missing prospects to database"""

    print("=" * 60)
    print("ADDING PRIORITY 3 PROSPECTS TO DATABASE")
    print("=" * 60)

    added = []
    already_exists = []
    errors = []

    with engine.connect() as conn:
        for prospect in PROSPECTS_TO_ADD:
            name = prospect['name']
            mlb_id = prospect['mlb_id']

            print(f"\nProcessing: {name} (MLB ID: {mlb_id})")

            try:
                # Check if already exists
                result = conn.execute(text('''
                    SELECT id, name FROM prospects
                    WHERE mlb_player_id = :mlb_id
                '''), {'mlb_id': mlb_id})

                existing = result.fetchone()
                if existing:
                    print(f"  [EXISTS] Already exists as: {existing[1]}")
                    already_exists.append({**prospect, 'existing_name': existing[1]})
                else:
                    # Add to database
                    conn.execute(text('''
                        INSERT INTO prospects (
                            name, mlb_player_id, position, organization,
                            current_level, created_at, updated_at
                        ) VALUES (
                            :name, :mlb_id, :position, :team,
                            :level, NOW(), NOW()
                        )
                    '''), {
                        'name': name,
                        'mlb_id': mlb_id,
                        'position': prospect['position'],
                        'team': prospect['team'],
                        'level': prospect['level']
                    })
                    conn.commit()
                    print(f"  [ADDED] Successfully added to database")
                    added.append(prospect)

            except Exception as e:
                print(f"  [ERROR] {e}")
                errors.append({**prospect, 'error': str(e)})

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Successfully added: {len(added)}")
    print(f"Already existed: {len(already_exists)}")
    print(f"Errors: {len(errors)}")

    if added:
        print("\nNewly added prospects:")
        for p in added:
            print(f"  - Rank #{p['rank']}: {p['name']} ({p['team']})")

    if already_exists:
        print("\nAlready in database:")
        for p in already_exists:
            print(f"  - {p['name']} exists as {p['existing_name']}")

    return added, already_exists, errors

def check_for_diacritic_issues():
    """Check for other prospects that might have diacritic issues"""

    print("\n" + "=" * 60)
    print("CHECKING FOR DIACRITIC ISSUES IN DATABASE")
    print("=" * 60)

    # Read original CSV to get all names
    csv_path = r'C:\Users\lilra\Downloads\mlb-top-prospects.csv'
    df = pd.read_csv(csv_path, encoding='utf-8-sig', skiprows=1)

    with engine.connect() as conn:
        # Get all prospect names from database
        result = conn.execute(text('''
            SELECT DISTINCT name, mlb_player_id
            FROM prospects
            WHERE name IS NOT NULL
            ORDER BY name
        '''))

        db_names = {row[0].lower(): row[1] for row in result}
        db_names_no_accents = {remove_accents(name).lower(): mlb_id
                               for name, mlb_id in db_names.items()}

        potential_mismatches = []

        # Check each CSV name
        for csv_name in df['Prospect'].unique():
            csv_lower = csv_name.lower()
            csv_no_accent = remove_accents(csv_name).lower()

            # Check if name exists in any form
            found = False
            if csv_lower in db_names:
                found = True
            elif csv_no_accent in db_names_no_accents:
                # Found with different accents
                potential_mismatches.append({
                    'csv_name': csv_name,
                    'type': 'accent_variation',
                    'matched_to': [name for name in db_names.keys()
                                  if remove_accents(name).lower() == csv_no_accent][0]
                })
                found = True

            # Check variations
            if not found:
                for variation in check_name_variations(csv_name):
                    if variation.lower() in db_names:
                        potential_mismatches.append({
                            'csv_name': csv_name,
                            'type': 'name_variation',
                            'matched_to': variation
                        })
                        found = True
                        break

        print(f"\nFound {len(potential_mismatches)} potential name mismatches due to diacritics")

        if potential_mismatches:
            print("\nSample mismatches:")
            for mismatch in potential_mismatches[:10]:
                print(f"  CSV: {mismatch['csv_name']} -> DB: {mismatch['matched_to']} ({mismatch['type']})")

        return potential_mismatches

def main():
    # Add prospects
    added, existed, errors = add_prospects_to_database()

    # Check for diacritic issues
    mismatches = check_for_diacritic_issues()

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if added:
        pd.DataFrame(added).to_csv(f'added_prospects_{timestamp}.csv', index=False)
        print(f"\nAdded prospects saved to: added_prospects_{timestamp}.csv")

    if mismatches:
        pd.DataFrame(mismatches).to_csv(f'name_mismatches_{timestamp}.csv', index=False)
        print(f"Name mismatches saved to: name_mismatches_{timestamp}.csv")

    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    print("1. Implement fuzzy name matching for future imports")
    print("2. Normalize names by removing accents during comparison")
    print("3. Store both original and normalized names in database")
    print("4. Consider using Levenshtein distance for name matching")

if __name__ == "__main__":
    main()