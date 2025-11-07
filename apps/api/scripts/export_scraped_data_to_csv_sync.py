"""
Export all scraped MILB game log and pitch data to CSV files (Synchronous version).

This script exports the following tables to CSV:
1. prospect_stats - Season-level aggregated statistics
2. milb_game_logs - Complete game-level statistics from MLB API
3. milb_batter_pitches - Individual pitches seen by batters
4. milb_pitcher_pitches - Individual pitches thrown by pitchers

Usage:
    python apps/api/scripts/export_scraped_data_to_csv_sync.py --database-url "postgresql://..."

Output:
    Creates CSV files in ./data_exports/ directory
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
import psycopg2
from psycopg2.extras import RealDictCursor


def export_table_to_csv(
    conn,
    table_name: str,
    output_dir: Path,
    limit: int | None = None,
    batch_size: int = 10000
) -> Dict[str, Any]:
    """
    Export a database table to CSV file using cursor batching.

    Args:
        conn: Database connection
        table_name: Name of the table to export
        output_dir: Directory to save CSV files
        limit: Optional limit on number of rows (for testing)
        batch_size: Number of rows to fetch per batch

    Returns:
        Dictionary with export statistics
    """
    print(f"\n{'='*60}")
    print(f"Exporting {table_name}...")
    print(f"{'='*60}")

    start_time = datetime.now()

    # Build query
    query = f"SELECT * FROM {table_name}"
    if limit:
        query += f" LIMIT {limit}"

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor, name=f'export_{table_name}')
        cursor.itersize = batch_size  # Server-side cursor batch size

        # Execute query
        cursor.execute(query)

        # Get column names from first batch
        first_batch = cursor.fetchmany(batch_size)
        if not first_batch:
            print(f"WARNING: No data found in {table_name}")
            cursor.close()
            return {
                "table": table_name,
                "rows_exported": 0,
                "file_path": None,
                "duration_seconds": 0,
                "status": "empty"
            }

        columns = first_batch[0].keys()

        # Create output file
        output_file = output_dir / f"{table_name}.csv"

        # Write to CSV in batches
        total_rows = 0
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columns)
            writer.writeheader()

            # Write first batch
            writer.writerows(first_batch)
            total_rows += len(first_batch)

            # Write remaining batches
            while True:
                batch = cursor.fetchmany(batch_size)
                if not batch:
                    break

                writer.writerows(batch)
                total_rows += len(batch)

                # Progress indicator
                if total_rows % 50000 == 0:
                    print(f"   Progress: {total_rows:,} rows exported...")

        cursor.close()

        duration = (datetime.now() - start_time).total_seconds()
        file_size_mb = output_file.stat().st_size / (1024 * 1024)

        print(f"SUCCESS: Exported {total_rows:,} rows")
        print(f"File: {output_file}")
        print(f"Size: {file_size_mb:.2f} MB")
        print(f"Duration: {duration:.2f} seconds")

        return {
            "table": table_name,
            "rows_exported": total_rows,
            "file_path": str(output_file),
            "file_size_mb": round(file_size_mb, 2),
            "duration_seconds": round(duration, 2),
            "status": "success"
        }

    except Exception as e:
        print(f"ERROR exporting {table_name}: {str(e)}")
        return {
            "table": table_name,
            "rows_exported": 0,
            "file_path": None,
            "error": str(e),
            "status": "error"
        }


def get_table_info(conn, table_name: str) -> Dict[str, Any]:
    """
    Get information about a table.

    Args:
        conn: Database connection
        table_name: Name of the table

    Returns:
        Dictionary with table information
    """
    try:
        cursor = conn.cursor()

        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]

        # Get table size
        cursor.execute("""
            SELECT
                pg_size_pretty(pg_total_relation_size(%s::regclass)) as total_size,
                pg_size_pretty(pg_relation_size(%s::regclass)) as table_size,
                pg_size_pretty(pg_total_relation_size(%s::regclass) - pg_relation_size(%s::regclass)) as indexes_size
        """, (table_name, table_name, table_name, table_name))
        size_info = cursor.fetchone()

        cursor.close()

        return {
            "table": table_name,
            "row_count": row_count,
            "total_size": size_info[0] if size_info else "N/A",
            "table_size": size_info[1] if size_info else "N/A",
            "indexes_size": size_info[2] if size_info else "N/A"
        }
    except Exception as e:
        return {
            "table": table_name,
            "error": str(e)
        }


def main(database_url: str, limit: int | None = None) -> None:
    """
    Main export function.

    Args:
        database_url: PostgreSQL database URL
        limit: Optional limit on rows per table (for testing)
    """
    print("\n" + "="*60)
    print("MILB Data Export Tool (Synchronous)")
    print("="*60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Database: {database_url}")
    if limit:
        print(f"WARNING: LIMIT MODE - Exporting max {limit:,} rows per table")
    print("="*60)

    # Create output directory
    output_dir = Path("./data_exports")
    output_dir.mkdir(exist_ok=True)
    print(f"\nOutput directory: {output_dir.absolute()}")

    # Tables to export
    tables = [
        "prospect_stats",
        "milb_game_logs",
        "milb_batter_pitches",
        "milb_pitcher_pitches"
    ]

    # Convert asyncpg URL to psycopg2 format
    db_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    try:
        # Connect to database
        print("\nConnecting to database...")
        conn = psycopg2.connect(db_url)
        print("Connected successfully!")

        # Get table information first
        print("\n" + "="*60)
        print("Database Table Information")
        print("="*60)

        table_info_list = []
        for table_name in tables:
            info = get_table_info(conn, table_name)
            table_info_list.append(info)

            if "error" in info:
                print(f"\nERROR {table_name}: {info['error']}")
            else:
                print(f"\n{table_name}")
                print(f"   Rows: {info['row_count']:,}")
                print(f"   Total Size: {info['total_size']}")
                print(f"   Table Size: {info['table_size']}")
                print(f"   Indexes Size: {info['indexes_size']}")

        # Export each table
        export_results = []
        for table_name in tables:
            result = export_table_to_csv(
                conn,
                table_name,
                output_dir,
                limit
            )
            export_results.append(result)

        # Print summary
        print("\n" + "="*60)
        print("Export Summary")
        print("="*60)

        total_rows = 0
        total_size_mb = 0
        success_count = 0

        for result in export_results:
            if result["status"] == "success":
                success_count += 1
                total_rows += result["rows_exported"]
                total_size_mb += result.get("file_size_mb", 0)

                print(f"\nSUCCESS {result['table']}")
                print(f"   Rows: {result['rows_exported']:,}")
                print(f"   Size: {result['file_size_mb']:.2f} MB")
                print(f"   Duration: {result['duration_seconds']:.2f}s")
                print(f"   File: {result['file_path']}")
            elif result["status"] == "empty":
                print(f"\nWARNING {result['table']}: No data")
            else:
                print(f"\nERROR {result['table']}: {result.get('error', 'Unknown error')}")

        print("\n" + "="*60)
        print(f"Export Complete!")
        print(f"   Tables exported: {success_count}/{len(tables)}")
        print(f"   Total rows: {total_rows:,}")
        print(f"   Total size: {total_size_mb:.2f} MB")
        print(f"   Output directory: {output_dir.absolute()}")
        print("="*60 + "\n")

        conn.close()

    except Exception as e:
        print(f"\nFATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export MILB data to CSV files (synchronous)")
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of rows per table (for testing)",
        default=None
    )
    parser.add_argument(
        "--database-url",
        type=str,
        required=True,
        help="PostgreSQL database URL (required)"
    )

    args = parser.parse_args()

    main(database_url=args.database_url, limit=args.limit)
