"""
Fantrax Cookie Authentication Service

Handles cookie-based authentication for Fantrax using Selenium
to allow users to log in to their Fantrax accounts.
"""

import pickle
import logging
from typing import Optional
from pathlib import Path
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.db.models import User
from app.core.security import encrypt_value

logger = logging.getLogger(__name__)


class FantraxCookieService:
    """Service for managing Fantrax cookie-based authentication"""

    FANTRAX_LOGIN_URL = "https://www.fantrax.com/login"
    COOKIE_EXPIRY_DAYS = 30

    @staticmethod
    def generate_cookie_file(output_path: str = "fantrax_login.cookie") -> bool:
        """
        Generate Fantrax login cookie using Selenium

        Opens a Chrome browser window where the user can log in to Fantrax.
        After 30 seconds, saves the cookies to a file.

        @param output_path - Path to save the cookie file
        @returns True if successful, False otherwise

        @since 1.0.0
        """
        try:
            logger.info("Starting Fantrax cookie generation")

            # Configure Chrome options
            chrome_options = Options()
            # Comment this out to see the browser window
            # chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")

            # Initialize Chrome driver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)

            try:
                # Navigate to Fantrax login page
                driver.get(FantraxCookieService.FANTRAX_LOGIN_URL)
                logger.info(f"Opened Fantrax login page: {FantraxCookieService.FANTRAX_LOGIN_URL}")

                # Wait for user to log in (30 seconds)
                import time
                logger.info("Please log in to Fantrax in the browser window...")
                logger.info("You have 30 seconds to complete the login")
                time.sleep(30)

                # Get cookies
                cookies = driver.get_cookies()
                logger.info(f"Retrieved {len(cookies)} cookies")

                # Save cookies to file
                with open(output_path, "wb") as f:
                    pickle.dump(cookies, f)

                logger.info(f"Cookies saved to {output_path}")
                return True

            finally:
                driver.quit()

        except Exception as e:
            logger.error(f"Failed to generate Fantrax cookie: {str(e)}")
            return False

    @staticmethod
    async def store_user_cookies(
        db: AsyncSession,
        user_id: int,
        cookie_path: str
    ) -> bool:
        """
        Store user's Fantrax cookies in database

        @param db - Database session
        @param user_id - User ID
        @param cookie_path - Path to cookie file

        @returns True if successful, False otherwise

        @since 1.0.0
        """
        try:
            # Read cookie file
            with open(cookie_path, "rb") as f:
                cookies = pickle.load(f)

            # Serialize cookies to JSON string
            import json
            cookies_json = json.dumps(cookies)

            # Encrypt cookies
            encrypted_cookies = encrypt_value(cookies_json)

            # Update user record
            stmt = (
                update(User)
                .where(User.id == user_id)
                .values(
                    fantrax_cookies=encrypted_cookies,
                    fantrax_connected_at=datetime.utcnow()
                )
            )
            await db.execute(stmt)
            await db.commit()

            logger.info(f"Stored Fantrax cookies for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store Fantrax cookies: {str(e)}")
            await db.rollback()
            return False

    @staticmethod
    async def get_user_cookies(db: AsyncSession, user_id: int) -> Optional[list]:
        """
        Retrieve user's Fantrax cookies from database

        @param db - Database session
        @param user_id - User ID

        @returns List of cookies or None if not found

        @since 1.0.0
        """
        try:
            # Get user record
            stmt = select(User).where(User.id == user_id)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user or not user.fantrax_cookies:
                logger.warning(f"No Fantrax cookies found for user {user_id}")
                return None

            # Decrypt and deserialize cookies
            from app.core.security import decrypt_value
            import json

            cookies_json = decrypt_value(user.fantrax_cookies)
            cookies = json.loads(cookies_json)

            return cookies

        except Exception as e:
            logger.error(f"Failed to retrieve Fantrax cookies: {str(e)}")
            return None

    @staticmethod
    async def clear_user_cookies(db: AsyncSession, user_id: int) -> bool:
        """
        Clear user's Fantrax cookies from database

        @param db - Database session
        @param user_id - User ID

        @returns True if successful, False otherwise

        @since 1.0.0
        """
        try:
            stmt = (
                update(User)
                .where(User.id == user_id)
                .values(
                    fantrax_cookies=None,
                    fantrax_connected_at=None
                )
            )
            await db.execute(stmt)
            await db.commit()

            logger.info(f"Cleared Fantrax cookies for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to clear Fantrax cookies: {str(e)}")
            await db.rollback()
            return False
