"""Export service for generating CSV exports of prospect rankings."""

import csv
import io
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import HTTPException, status

from app.db.models import User


class ExportService:
    """Service for exporting prospect data in various formats."""

    @staticmethod
    def validate_export_access(user: User) -> bool:
        """
        Validate if user has access to export functionality.

        Args:
            user: User requesting export

        Returns:
            True if user has premium subscription

        Raises:
            HTTPException if user doesn't have access
        """
        if user.subscription_tier != 'premium':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSV export is only available for premium subscribers"
            )
        return True

    @staticmethod
    def generate_csv(
        prospects: List[Dict[str, Any]],
        include_advanced_metrics: bool = True
    ) -> str:
        """
        Generate CSV export of prospect rankings.

        Args:
            prospects: List of prospect dictionaries with ranking data
            include_advanced_metrics: Include ML scores and advanced metrics

        Returns:
            CSV string
        """
        output = io.StringIO()

        # Define columns based on what to include
        base_columns = [
            'Dynasty Rank',
            'Name',
            'Position',
            'Organization',
            'Level',
            'Age',
            'ETA Year',
            'Dynasty Score'
        ]

        advanced_columns = [
            'ML Score',
            'Scouting Score',
            'Confidence Level',
            'Batting Average',
            'On-Base %',
            'Slugging %',
            'ERA',
            'WHIP',
            'Overall Grade',
            'Future Value'
        ]

        columns = base_columns
        if include_advanced_metrics:
            columns.extend(advanced_columns)

        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()

        for prospect in prospects:
            row = {
                'Dynasty Rank': prospect.get('dynasty_rank', ''),
                'Name': prospect.get('name', ''),
                'Position': prospect.get('position', ''),
                'Organization': prospect.get('organization', ''),
                'Level': prospect.get('level', ''),
                'Age': prospect.get('age', ''),
                'ETA Year': prospect.get('eta_year', ''),
                'Dynasty Score': f"{prospect.get('dynasty_score', 0):.2f}"
            }

            if include_advanced_metrics:
                row.update({
                    'ML Score': f"{prospect.get('ml_score', 0):.2f}",
                    'Scouting Score': f"{prospect.get('scouting_score', 0):.2f}",
                    'Confidence Level': prospect.get('confidence_level', 'Low'),
                    'Batting Average': f"{prospect.get('batting_avg'):.3f}" if prospect.get('batting_avg') is not None else '',
                    'On-Base %': f"{prospect.get('on_base_pct'):.3f}" if prospect.get('on_base_pct') is not None else '',
                    'Slugging %': f"{prospect.get('slugging_pct'):.3f}" if prospect.get('slugging_pct') is not None else '',
                    'ERA': f"{prospect.get('era'):.2f}" if prospect.get('era') is not None else '',
                    'WHIP': f"{prospect.get('whip'):.2f}" if prospect.get('whip') is not None else '',
                    'Overall Grade': prospect.get('overall_grade', ''),
                    'Future Value': prospect.get('future_value', '')
                })

            writer.writerow(row)

        # Add metadata footer
        output.write(f"\n# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
        output.write("# Data provided by A Fine Wine Dynasty\n")
        output.write("# Dynasty scores calculated using proprietary algorithm combining ML predictions, scouting grades, and performance metrics\n")

        return output.getvalue()

    @staticmethod
    def generate_filename(
        filters: Optional[Dict[str, Any]] = None,
        prefix: str = "prospect_rankings"
    ) -> str:
        """
        Generate appropriate filename for export.

        Args:
            filters: Applied filters to include in filename
            prefix: Filename prefix

        Returns:
            Formatted filename with timestamp
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Add filter context to filename
        filter_parts = []
        if filters:
            if filters.get('position'):
                filter_parts.append(f"pos_{'_'.join(filters['position'][:2])}")
            if filters.get('organization'):
                filter_parts.append(f"org_{'_'.join(filters['organization'][:1])}")
            if filters.get('level'):
                filter_parts.append(f"lvl_{'_'.join(filters['level'][:1])}")

        if filter_parts:
            filter_str = "_" + "_".join(filter_parts)
        else:
            filter_str = ""

        return f"{prefix}{filter_str}_{timestamp}.csv"