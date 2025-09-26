#!/usr/bin/env python3
"""
Simple model validation that checks syntax and structure without dependencies.
"""

import ast
import sys
from pathlib import Path

def validate_python_syntax(file_path):
    """Validate that a Python file has correct syntax."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Parse the AST to check syntax
        ast.parse(source, filename=str(file_path))
        return True, "Syntax valid"

    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    except Exception as e:
        return False, f"Error reading file: {e}"

def analyze_model_file(file_path):
    """Analyze the models file for expected classes and structure."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        expected_classes = ['User', 'UserSession', 'Prospect', 'ProspectStats', 'ScoutingGrades', 'MLPrediction']
        found_classes = []

        for class_name in expected_classes:
            if f"class {class_name}(" in content:
                found_classes.append(class_name)

        return found_classes, expected_classes

    except Exception as e:
        return [], []

def main():
    """Main validation function."""
    print("Validating database models...")

    models_path = Path("app/db/models.py")

    # Check syntax
    is_valid, message = validate_python_syntax(models_path)
    if not is_valid:
        print(f"ERROR: Model syntax validation failed: {message}")
        return False

    print("SUCCESS: Model syntax is valid")

    # Check model classes
    found_classes, expected_classes = analyze_model_file(models_path)

    print(f"Expected classes: {', '.join(expected_classes)}")
    print(f"Found classes: {', '.join(found_classes)}")

    missing_classes = set(expected_classes) - set(found_classes)
    if missing_classes:
        print(f"ERROR: Missing classes: {', '.join(missing_classes)}")
        return False

    print("SUCCESS: All expected model classes found")

    # Check migration files
    migrations_path = Path("alembic/versions")
    migration_files = list(migrations_path.glob("*.py"))

    print(f"Found {len(migration_files)} migration files:")
    for migration_file in sorted(migration_files):
        print(f"  - {migration_file.name}")

    expected_migrations = 7  # We created migrations 001-007
    if len(migration_files) >= expected_migrations:
        print("SUCCESS: Expected migration files present")
    else:
        print(f"WARNING: Expected at least {expected_migrations} migrations, found {len(migration_files)}")

    print("SUCCESS: Model validation completed successfully!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)