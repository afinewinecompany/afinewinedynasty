"""
Feature Flag Service for Beta Features

Manages feature flags and beta feature access for premium users.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import json
import random
from enum import Enum

from app.db.models import User
from app.core.cache_manager import cache_manager
from app.core.config import settings
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)


class FeatureFlagStatus(Enum):
    """Feature flag status enumeration."""
    ENABLED = "enabled"
    DISABLED = "disabled"
    BETA = "beta"
    ROLLOUT = "rollout"
    DEPRECATED = "deprecated"


class FeatureFlagService:
    """
    Service for managing feature flags and beta features.

    Features:
    - Tier-based feature access control
    - Gradual rollout percentages
    - A/B testing support
    - User opt-in/opt-out management
    - Feature flag analytics
    """

    # Feature flag definitions
    DEFAULT_FEATURE_FLAGS = {
        "enhanced_outlooks": {
            "name": "Enhanced AI Outlooks",
            "description": "Personalized ML predictions with detailed explanations",
            "status": FeatureFlagStatus.ENABLED.value,
            "tiers": ["premium"],
            "rollout_percentage": 100,
            "beta": False
        },
        "historical_trends": {
            "name": "Historical Data Trends",
            "description": "Access to historical performance data and trends",
            "status": FeatureFlagStatus.ENABLED.value,
            "tiers": ["premium"],
            "rollout_percentage": 100,
            "beta": False
        },
        "advanced_comparisons": {
            "name": "Advanced Prospect Comparisons",
            "description": "Compare up to 10 prospects with detailed analytics",
            "status": FeatureFlagStatus.ENABLED.value,
            "tiers": ["premium"],
            "rollout_percentage": 100,
            "beta": False
        },
        "ml_explanations": {
            "name": "ML Prediction Explanations",
            "description": "SHAP-based explanations for ML predictions",
            "status": FeatureFlagStatus.BETA.value,
            "tiers": ["premium"],
            "rollout_percentage": 50,
            "beta": True
        },
        "custom_scoring": {
            "name": "Custom Scoring Models",
            "description": "Create custom scoring models for your league",
            "status": FeatureFlagStatus.BETA.value,
            "tiers": ["premium"],
            "rollout_percentage": 25,
            "beta": True
        },
        "api_access": {
            "name": "API Access",
            "description": "Programmatic API access for data retrieval",
            "status": FeatureFlagStatus.BETA.value,
            "tiers": ["premium"],
            "rollout_percentage": 10,
            "beta": True
        },
        "mobile_app": {
            "name": "Mobile App Beta",
            "description": "Early access to mobile application",
            "status": FeatureFlagStatus.ROLLOUT.value,
            "tiers": ["premium"],
            "rollout_percentage": 30,
            "beta": True
        },
        "slack_integration": {
            "name": "Slack Integration",
            "description": "Get prospect updates in Slack",
            "status": FeatureFlagStatus.DISABLED.value,
            "tiers": ["premium"],
            "rollout_percentage": 0,
            "beta": True
        }
    }

    @staticmethod
    async def get_feature_flags(
        user_id: Optional[int] = None,
        tier: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get all feature flags, optionally filtered by user/tier.

        Args:
            user_id: Optional user ID for personalized flags
            tier: Optional tier filter

        Returns:
            Dictionary of feature flags with status
        """
        # Try to get from Redis first
        cache_key = f"feature_flags:{tier or 'all'}:{user_id or 'all'}"

        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache read failed: {e}")

        # Build feature flag response
        flags = {}

        for flag_id, flag_config in FeatureFlagService.DEFAULT_FEATURE_FLAGS.items():
            # Check tier eligibility
            if tier and tier not in flag_config["tiers"]:
                continue

            flag_info = {
                "id": flag_id,
                "name": flag_config["name"],
                "description": flag_config["description"],
                "status": flag_config["status"],
                "enabled": False,
                "beta": flag_config["beta"]
            }

            # Determine if feature is enabled for this user/tier
            if flag_config["status"] == FeatureFlagStatus.ENABLED.value:
                flag_info["enabled"] = tier in flag_config["tiers"] if tier else True
            elif flag_config["status"] == FeatureFlagStatus.ROLLOUT.value:
                # Check rollout percentage
                if user_id:
                    flag_info["enabled"] = FeatureFlagService._is_in_rollout(
                        user_id,
                        flag_id,
                        flag_config["rollout_percentage"]
                    )
            elif flag_config["status"] == FeatureFlagStatus.BETA.value:
                # Beta features require opt-in
                flag_info["enabled"] = False
                if user_id:
                    flag_info["enabled"] = await FeatureFlagService._is_beta_enabled(
                        user_id,
                        flag_id
                    )

            flags[flag_id] = flag_info

        # Cache result for 5 minutes
        try:
            await redis_client.setex(
                cache_key,
                300,
                json.dumps(flags)
            )
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")

        return flags

    @staticmethod
    async def check_feature_access(
        db: AsyncSession,
        user_id: int,
        feature_id: str
    ) -> bool:
        """
        Check if a user has access to a specific feature.

        Args:
            db: Database session
            user_id: User ID
            feature_id: Feature flag ID

        Returns:
            Boolean indicating access
        """
        # Get user to check tier
        user_query = select(User).where(User.id == user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()

        if not user:
            return False

        tier = user.subscription_tier or "free"

        # Get feature configuration
        if feature_id not in FeatureFlagService.DEFAULT_FEATURE_FLAGS:
            return False

        feature_config = FeatureFlagService.DEFAULT_FEATURE_FLAGS[feature_id]

        # Check tier eligibility
        if tier not in feature_config["tiers"]:
            return False

        # Check feature status
        if feature_config["status"] == FeatureFlagStatus.DISABLED.value:
            return False

        if feature_config["status"] == FeatureFlagStatus.ENABLED.value:
            return True

        if feature_config["status"] == FeatureFlagStatus.ROLLOUT.value:
            return FeatureFlagService._is_in_rollout(
                user_id,
                feature_id,
                feature_config["rollout_percentage"]
            )

        if feature_config["status"] == FeatureFlagStatus.BETA.value:
            return await FeatureFlagService._is_beta_enabled(user_id, feature_id)

        return False

    @staticmethod
    async def enable_beta_feature(
        db: AsyncSession,
        user_id: int,
        feature_id: str
    ) -> bool:
        """
        Enable a beta feature for a user.

        Args:
            db: Database session
            user_id: User ID
            feature_id: Feature flag ID

        Returns:
            Success status
        """
        # Get user
        user_query = select(User).where(User.id == user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()

        if not user:
            return False

        # Check if feature exists and is beta
        if feature_id not in FeatureFlagService.DEFAULT_FEATURE_FLAGS:
            return False

        feature_config = FeatureFlagService.DEFAULT_FEATURE_FLAGS[feature_id]
        if not feature_config["beta"]:
            return False

        # Check tier eligibility
        tier = user.subscription_tier or "free"
        if tier not in feature_config["tiers"]:
            return False

        # Store beta opt-in in user preferences
        if not user.preferences:
            user.preferences = {}

        if "beta_features" not in user.preferences:
            user.preferences["beta_features"] = {}

        user.preferences["beta_features"][feature_id] = {
            "enabled": True,
            "opted_in_at": datetime.utcnow().isoformat()
        }

        # Mark preferences as modified for SQLAlchemy to detect change
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(user, "preferences")

        await db.commit()

        # Clear cache
        cache_key = f"beta_features:{user_id}"
        try:
            await redis_client.delete(cache_key)
        except:
            pass

        return True

    @staticmethod
    async def disable_beta_feature(
        db: AsyncSession,
        user_id: int,
        feature_id: str
    ) -> bool:
        """
        Disable a beta feature for a user.

        Args:
            db: Database session
            user_id: User ID
            feature_id: Feature flag ID

        Returns:
            Success status
        """
        # Get user
        user_query = select(User).where(User.id == user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()

        if not user or not user.preferences:
            return False

        # Remove beta opt-in
        if "beta_features" in user.preferences and feature_id in user.preferences["beta_features"]:
            user.preferences["beta_features"][feature_id] = {
                "enabled": False,
                "opted_out_at": datetime.utcnow().isoformat()
            }

            # Mark preferences as modified
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(user, "preferences")

            await db.commit()

            # Clear cache
            cache_key = f"beta_features:{user_id}"
            try:
                await redis_client.delete(cache_key)
            except:
                pass

            return True

        return False

    @staticmethod
    async def get_user_beta_features(
        db: AsyncSession,
        user_id: int
    ) -> List[str]:
        """
        Get list of beta features enabled for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            List of enabled beta feature IDs
        """
        # Check cache first
        cache_key = f"beta_features:{user_id}"
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except:
            pass

        # Get user
        user_query = select(User).where(User.id == user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()

        if not user or not user.preferences:
            return []

        beta_features = []
        if "beta_features" in user.preferences:
            for feature_id, config in user.preferences["beta_features"].items():
                if config.get("enabled", False):
                    beta_features.append(feature_id)

        # Cache for 15 minutes
        try:
            await redis_client.setex(
                cache_key,
                900,
                json.dumps(beta_features)
            )
        except:
            pass

        return beta_features

    @staticmethod
    def _is_in_rollout(user_id: int, feature_id: str, percentage: int) -> bool:
        """
        Check if user is in rollout percentage for a feature.

        Uses consistent hashing to ensure same result for same user/feature.

        Args:
            user_id: User ID
            feature_id: Feature flag ID
            percentage: Rollout percentage (0-100)

        Returns:
            Boolean indicating if user is in rollout
        """
        if percentage >= 100:
            return True
        if percentage <= 0:
            return False

        # Use consistent hash for deterministic rollout
        hash_input = f"{user_id}:{feature_id}"
        hash_value = hash(hash_input)

        # Convert to percentage (0-100)
        user_percentage = abs(hash_value) % 100

        return user_percentage < percentage

    @staticmethod
    async def _is_beta_enabled(user_id: int, feature_id: str) -> bool:
        """
        Check if user has opted into a beta feature.

        Args:
            user_id: User ID
            feature_id: Feature flag ID

        Returns:
            Boolean indicating if beta feature is enabled
        """
        # Check cache
        cache_key = f"beta_feature:{user_id}:{feature_id}"
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return cached == "true"
        except:
            pass

        # This would typically check the database
        # For now, return False as default
        return False

    @staticmethod
    async def track_feature_usage(
        user_id: int,
        feature_id: str,
        action: str = "view"
    ) -> None:
        """
        Track feature usage for analytics.

        Args:
            user_id: User ID
            feature_id: Feature flag ID
            action: Action type (view, click, etc.)
        """
        try:
            # Store usage data in Redis for aggregation
            key = f"feature_usage:{feature_id}:{datetime.utcnow().strftime('%Y%m%d')}"
            await redis_client.hincrby(key, f"{user_id}:{action}", 1)

            # Set expiry for 30 days
            await redis_client.expire(key, 2592000)
        except Exception as e:
            logger.warning(f"Failed to track feature usage: {e}")

    @staticmethod
    async def get_feature_analytics(
        feature_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get feature usage analytics.

        Args:
            feature_id: Feature flag ID
            days: Number of days to analyze

        Returns:
            Analytics data for the feature
        """
        analytics = {
            "feature_id": feature_id,
            "period_days": days,
            "total_usage": 0,
            "unique_users": set(),
            "daily_usage": {}
        }

        try:
            # Collect usage data from Redis
            for i in range(days):
                date = (datetime.utcnow() - timedelta(days=i)).strftime('%Y%m%d')
                key = f"feature_usage:{feature_id}:{date}"

                usage_data = await redis_client.hgetall(key)
                if usage_data:
                    daily_total = 0
                    for user_action, count in usage_data.items():
                        user_id = user_action.split(':')[0]
                        analytics["unique_users"].add(user_id)
                        daily_total += int(count)
                        analytics["total_usage"] += int(count)

                    analytics["daily_usage"][date] = daily_total

            analytics["unique_users"] = len(analytics["unique_users"])

        except Exception as e:
            logger.error(f"Failed to get feature analytics: {e}")

        return analytics