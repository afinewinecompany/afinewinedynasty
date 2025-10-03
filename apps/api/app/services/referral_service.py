"""
Referral service for code generation and tracking.

@module referral_service
@since 1.0.0
"""

import secrets
import string
from datetime import datetime
from typing import Optional, Dict, Any
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

logger = logging.getLogger(__name__)


class ReferralService:
    """
    Manages referral code generation and tracking.

    @class ReferralService
    @since 1.0.0
    """

    def __init__(self, db: AsyncSession):
        """Initialize referral service."""
        self.db = db

    def _generate_code(self, length: int = 8) -> str:
        """Generate unique referral code."""
        chars = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))

    async def get_or_create_referral_code(self, user_id: int) -> str:
        """
        Get existing referral code or create new one.

        @param user_id - User ID
        @returns Referral code string
        """
        try:
            from app.db.models import ReferralCode

            # Check for existing code
            stmt = select(ReferralCode).where(ReferralCode.user_id == user_id)
            result = await self.db.execute(stmt)
            existing_code = result.scalar_one_or_none()

            if existing_code:
                logger.debug(f"Found existing referral code for user {user_id}")
                return existing_code.code

            # Create new code
            code = self._generate_code()

            # Ensure code is unique
            while True:
                stmt = select(ReferralCode).where(ReferralCode.code == code)
                result = await self.db.execute(stmt)
                if result.scalar_one_or_none() is None:
                    break
                code = self._generate_code()

            # Insert new referral code
            referral_code = ReferralCode(
                user_id=user_id,
                code=code,
                uses_remaining=10
            )
            self.db.add(referral_code)
            await self.db.commit()

            logger.info(f"Generated referral code {code} for user {user_id}")
            return code

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to get/create referral code for user {user_id}: {str(e)}")
            raise

    async def validate_referral_code(self, code: str) -> Optional[int]:
        """
        Validate referral code and return referrer user ID.

        @param code - Referral code to validate
        @returns Referrer user ID if valid, None otherwise
        """
        try:
            from app.db.models import ReferralCode

            # Query for the referral code
            stmt = select(ReferralCode).where(ReferralCode.code == code)
            result = await self.db.execute(stmt)
            referral_code = result.scalar_one_or_none()

            if not referral_code:
                logger.debug(f"Referral code not found: {code}")
                return None

            # Check if code has uses remaining
            if referral_code.uses_remaining <= 0:
                logger.debug(f"Referral code exhausted: {code}")
                return None

            logger.debug(f"Valid referral code {code} for user {referral_code.user_id}")
            return referral_code.user_id

        except Exception as e:
            logger.error(f"Failed to validate referral code {code}: {str(e)}")
            return None

    async def get_referral_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Get referral statistics for user.

        @param user_id - User ID
        @returns Referral statistics
        """
        try:
            from app.db.models import Referral

            # Get user's referral code
            code = await self.get_or_create_referral_code(user_id)

            # Query all referrals made by this user
            stmt = select(Referral).where(Referral.referrer_id == user_id)
            result = await self.db.execute(stmt)
            referrals = result.scalars().all()

            # Calculate statistics
            total_referrals = len(referrals)
            successful_referrals = sum(1 for r in referrals if r.status == 'completed')
            pending_referrals = sum(1 for r in referrals if r.status == 'pending')
            rewards_earned = sum(1 for r in referrals if r.reward_granted)

            logger.debug(f"Referral stats for user {user_id}: {total_referrals} total, {successful_referrals} successful")

            return {
                "total_referrals": total_referrals,
                "successful_referrals": successful_referrals,
                "pending_referrals": pending_referrals,
                "rewards_earned": rewards_earned,
                "referral_code": code
            }

        except Exception as e:
            logger.error(f"Failed to get referral stats for user {user_id}: {str(e)}")
            # Return default values with code
            code = await self.get_or_create_referral_code(user_id)
            return {
                "total_referrals": 0,
                "successful_referrals": 0,
                "pending_referrals": 0,
                "rewards_earned": 0,
                "referral_code": code
            }

    async def create_referral(
        self,
        referrer_id: int,
        referred_user_id: int
    ) -> bool:
        """
        Create referral relationship.

        @param referrer_id - ID of user who referred
        @param referred_user_id - ID of new user
        @returns Success status
        """
        try:
            from app.db.models import Referral, ReferralCode

            # Create referral record
            referral = Referral(
                referrer_id=referrer_id,
                referred_user_id=referred_user_id,
                status='pending',
                reward_granted=False
            )
            self.db.add(referral)

            # Decrement uses_remaining on referral code
            stmt = select(ReferralCode).where(ReferralCode.user_id == referrer_id)
            result = await self.db.execute(stmt)
            referral_code = result.scalar_one_or_none()

            if referral_code and referral_code.uses_remaining > 0:
                referral_code.uses_remaining -= 1

            await self.db.commit()

            logger.info(f"Created referral: {referrer_id} -> {referred_user_id}")
            return True

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create referral {referrer_id} -> {referred_user_id}: {str(e)}")
            return False

    async def grant_referral_reward(self, referral_id: int) -> bool:
        """
        Grant reward for successful referral.

        @param referral_id - Referral record ID
        @returns Success status
        """
        logger.info(f"Granting reward for referral {referral_id}")
        # TODO: Update subscription or credits
        return True
