import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional
from statistics import mean, stdev
from pydantic import ValidationError

from app.schemas.prospect_schemas import (
    ProspectValidationSchema,
    ProspectStatsValidationSchema,
    HittingStatsValidationSchema,
    PitchingStatsValidationSchema,
    ValidationResult,
    DataQualityReport,
    MLBAPIPlayerResponse,
    MLBAPIStatsResponse
)

logger = logging.getLogger(__name__)


class DataValidationService:
    """Service for validating and cleaning prospect data."""

    def __init__(self):
        self.validation_stats = {
            "total_validated": 0,
            "validation_errors": {},
            "outliers_detected": [],
        }

        # Statistical thresholds for outlier detection
        self.outlier_thresholds = {
            "batting_avg": {"min": 0.100, "max": 0.500, "z_score": 3.0},
            "home_runs": {"min": 0, "max": 60, "z_score": 2.5},
            "era": {"min": 0.50, "max": 10.0, "z_score": 3.0},
            "strikeouts_per_nine": {"min": 3.0, "max": 18.0, "z_score": 2.5},
            "woba": {"min": 0.200, "max": 0.500, "z_score": 2.5},
            "wrc_plus": {"min": 40, "max": 200, "z_score": 2.5}
        }

    async def validate_mlb_api_response(self, response_data: Dict[str, Any], response_type: str) -> ValidationResult:
        """
        Validate MLB API response data.

        Args:
            response_data: Raw response from MLB API
            response_type: Type of response ('player' or 'stats')

        Returns:
            ValidationResult with validation status and errors
        """
        errors = []
        warnings = []

        try:
            if response_type == "player":
                # Validate player data structure
                if "people" in response_data:
                    for player in response_data["people"]:
                        try:
                            MLBAPIPlayerResponse(**player)
                        except ValidationError as e:
                            errors.extend([f"Player {player.get('id', 'unknown')}: {error['msg']}" for error in e.errors()])
                else:
                    errors.append("Missing 'people' field in player response")

            elif response_type == "stats":
                # Validate stats data structure
                try:
                    MLBAPIStatsResponse(**response_data)
                except ValidationError as e:
                    errors.extend([error["msg"] for error in e.errors()])

            else:
                errors.append(f"Unknown response type: {response_type}")

        except Exception as e:
            errors.append(f"Validation error: {str(e)}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            data_quality_score=1.0 if len(errors) == 0 else max(0.0, 1.0 - len(errors) * 0.1),
            outliers_detected=[]
        )

    async def validate_prospect_data(self, prospect_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate prospect data before database insertion.

        Args:
            prospect_data: Prospect data dictionary

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        outliers = []

        try:
            # Validate using Pydantic schema
            validated_prospect = ProspectValidationSchema(**prospect_data)

            # Additional business logic validation
            if validated_prospect.age and validated_prospect.eta_year:
                expected_eta = datetime.now().year + max(0, 25 - validated_prospect.age)
                if abs(validated_prospect.eta_year - expected_eta) > 5:
                    warnings.append(f"ETA year {validated_prospect.eta_year} seems inconsistent with age {validated_prospect.age}")

            # Check for missing critical fields
            if not validated_prospect.organization:
                warnings.append("Missing organization information")

            if not validated_prospect.level:
                warnings.append("Missing minor league level")

        except ValidationError as e:
            errors.extend([error["msg"] for error in e.errors()])

        # Data quality score calculation
        quality_score = self._calculate_quality_score(prospect_data, errors, warnings)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            data_quality_score=quality_score,
            outliers_detected=outliers
        )

    async def validate_stats_data(self, stats_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate prospect statistics data.

        Args:
            stats_data: Statistics data dictionary

        Returns:
            ValidationResult with validation status and outlier detection
        """
        errors = []
        warnings = []
        outliers = []

        try:
            # Validate using Pydantic schema
            validated_stats = ProspectStatsValidationSchema(**stats_data)

            # Statistical outlier detection
            outliers = self._detect_statistical_outliers(stats_data)

            # Cross-field consistency checks
            consistency_errors = self._check_stats_consistency(stats_data)
            errors.extend(consistency_errors)

            # Performance anomaly detection
            anomaly_warnings = self._detect_performance_anomalies(stats_data)
            warnings.extend(anomaly_warnings)

        except ValidationError as e:
            errors.extend([error["msg"] for error in e.errors()])

        # Data quality score calculation
        quality_score = self._calculate_stats_quality_score(stats_data, errors, warnings, outliers)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            data_quality_score=quality_score,
            outliers_detected=outliers
        )

    def _detect_statistical_outliers(self, stats_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect statistical outliers in performance metrics.

        Args:
            stats_data: Statistics data

        Returns:
            List of detected outliers with details
        """
        outliers = []

        for metric, thresholds in self.outlier_thresholds.items():
            value = stats_data.get(metric)
            if value is None:
                continue

            # Range-based outlier detection
            if value < thresholds["min"] or value > thresholds["max"]:
                outliers.append({
                    "metric": metric,
                    "value": value,
                    "type": "range_outlier",
                    "expected_range": f"{thresholds['min']}-{thresholds['max']}",
                    "severity": "high" if value < thresholds["min"] * 0.5 or value > thresholds["max"] * 1.5 else "medium"
                })

            # Performance-based outlier detection for specific metrics
            if metric == "batting_avg" and value > 0.400:
                outliers.append({
                    "metric": metric,
                    "value": value,
                    "type": "exceptional_performance",
                    "note": "Exceptionally high batting average",
                    "severity": "low"
                })

            if metric == "era" and value < 1.00:
                outliers.append({
                    "metric": metric,
                    "value": value,
                    "type": "exceptional_performance",
                    "note": "Exceptionally low ERA",
                    "severity": "low"
                })

        return outliers

    def _check_stats_consistency(self, stats_data: Dict[str, Any]) -> List[str]:
        """
        Check consistency between related statistical fields.

        Args:
            stats_data: Statistics data

        Returns:
            List of consistency error messages
        """
        errors = []

        # Hitting consistency checks
        at_bats = stats_data.get("at_bats")
        hits = stats_data.get("hits")
        home_runs = stats_data.get("home_runs")
        walks = stats_data.get("walks")
        strikeouts = stats_data.get("strikeouts")

        if at_bats and hits:
            if hits > at_bats:
                errors.append("Hits cannot exceed at-bats")

        if hits and home_runs:
            if home_runs > hits:
                errors.append("Home runs cannot exceed hits")

        if at_bats and walks and strikeouts:
            total_plate_appearances = at_bats + walks
            if strikeouts > total_plate_appearances:
                errors.append("Strikeouts cannot exceed total plate appearances")

        # Pitching consistency checks
        innings = stats_data.get("innings_pitched")
        earned_runs = stats_data.get("earned_runs")
        era = stats_data.get("era")

        if all(v is not None for v in [innings, earned_runs, era]) and innings > 0:
            calculated_era = (earned_runs * 9) / innings
            if abs(era - calculated_era) > 0.1:
                errors.append(f"ERA {era} inconsistent with calculated ERA {calculated_era:.2f}")

        return errors

    def _detect_performance_anomalies(self, stats_data: Dict[str, Any]) -> List[str]:
        """
        Detect performance anomalies that might indicate data quality issues.

        Args:
            stats_data: Statistics data

        Returns:
            List of anomaly warning messages
        """
        warnings = []

        # Check for unusual performance combinations
        batting_avg = stats_data.get("batting_avg")
        home_runs = stats_data.get("home_runs")
        stolen_bases = stats_data.get("stolen_bases")

        if batting_avg and home_runs and stolen_bases:
            # Unusual combination: very high power and speed
            if home_runs > 20 and stolen_bases > 20 and batting_avg > 0.300:
                warnings.append("Unusual combination of power, speed, and contact - verify data")

        # Check for extreme ratios
        strikeouts = stats_data.get("strikeouts")
        walks = stats_data.get("walks")

        if strikeouts and walks and walks > 0:
            k_bb_ratio = strikeouts / walks
            if k_bb_ratio > 10:
                warnings.append(f"Very high strikeout-to-walk ratio ({k_bb_ratio:.1f}) - verify data")

        return warnings

    def _calculate_quality_score(self, data: Dict[str, Any], errors: List[str], warnings: List[str]) -> float:
        """Calculate data quality score for prospect data."""
        base_score = 1.0

        # Deduct points for errors and warnings
        error_penalty = len(errors) * 0.2
        warning_penalty = len(warnings) * 0.05

        # Deduct points for missing fields
        required_fields = ["mlb_id", "name", "position"]
        missing_required = sum(1 for field in required_fields if not data.get(field))
        missing_penalty = missing_required * 0.1

        # Deduct points for missing optional but important fields
        optional_fields = ["organization", "level", "age"]
        missing_optional = sum(1 for field in optional_fields if not data.get(field))
        optional_penalty = missing_optional * 0.05

        final_score = base_score - error_penalty - warning_penalty - missing_penalty - optional_penalty
        return max(0.0, min(1.0, final_score))

    def _calculate_stats_quality_score(
        self,
        data: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
        outliers: List[Dict[str, Any]]
    ) -> float:
        """Calculate data quality score for statistics data."""
        base_score = 1.0

        # Deduct points for validation errors
        error_penalty = len(errors) * 0.25

        # Deduct points for warnings
        warning_penalty = len(warnings) * 0.05

        # Deduct points for outliers based on severity
        outlier_penalty = 0.0
        for outlier in outliers:
            severity = outlier.get("severity", "medium")
            if severity == "high":
                outlier_penalty += 0.15
            elif severity == "medium":
                outlier_penalty += 0.05
            else:  # low
                outlier_penalty += 0.02

        # Reward completeness
        stats_fields = [
            "games_played", "at_bats", "hits", "home_runs", "rbi",
            "batting_avg", "on_base_pct", "slugging_pct"
        ]
        completeness = sum(1 for field in stats_fields if data.get(field) is not None) / len(stats_fields)
        completeness_bonus = (completeness - 0.5) * 0.1  # Bonus for > 50% completeness

        final_score = base_score - error_penalty - warning_penalty - outlier_penalty + completeness_bonus
        return max(0.0, min(1.0, final_score))

    async def generate_quality_report(
        self,
        validation_results: List[ValidationResult]
    ) -> DataQualityReport:
        """
        Generate comprehensive data quality report.

        Args:
            validation_results: List of validation results

        Returns:
            DataQualityReport with summary statistics
        """
        total_records = len(validation_results)
        valid_records = sum(1 for result in validation_results if result.is_valid)
        invalid_records = total_records - valid_records

        # Aggregate error types
        error_counts = {}
        outlier_counts = {}

        for result in validation_results:
            for error in result.errors:
                error_type = error.split(":")[0] if ":" in error else error
                error_counts[error_type] = error_counts.get(error_type, 0) + 1

            for outlier in result.outliers_detected:
                outlier_type = outlier.get("type", "unknown")
                outlier_counts[outlier_type] = outlier_counts.get(outlier_type, 0) + 1

        # Calculate overall quality score
        if total_records > 0:
            quality_scores = [result.data_quality_score for result in validation_results]
            overall_quality = sum(quality_scores) / len(quality_scores)
        else:
            overall_quality = 0.0

        # Generate recommendations
        recommendations = []
        if invalid_records > total_records * 0.1:
            recommendations.append("High error rate detected - review data source quality")

        if error_counts.get("range_outlier", 0) > total_records * 0.05:
            recommendations.append("Multiple range outliers detected - verify data collection process")

        if overall_quality < 0.8:
            recommendations.append("Overall data quality below acceptable threshold - implement stricter validation")

        return DataQualityReport(
            total_records_validated=total_records,
            valid_records=valid_records,
            invalid_records=invalid_records,
            validation_errors=error_counts,
            outliers_summary=outlier_counts,
            overall_quality_score=overall_quality,
            recommendations=recommendations
        )


# Singleton instance
data_validation_service = DataValidationService()