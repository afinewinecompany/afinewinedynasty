"""
Fantrax Authentication Service

Handles server-side Selenium browser automation for Fantrax authentication.
Manages browser sessions, cookie capture, and resource cleanup.

@module fantrax_auth_service
@since 1.0.0
"""

import pickle
import logging
import asyncio
import os
from typing import Optional, Dict, List
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from app.db.models import User
from app.core.security import encrypt_value

logger = logging.getLogger(__name__)


class FantraxAuthService:
    """
    Service for managing Fantrax authentication via Selenium.

    Handles browser lifecycle, session management, cookie extraction,
    and secure storage of authentication credentials.

    Example:
        ```python
        service = FantraxAuthService()
        session = await service.create_auth_session(user_id=1, session_id="uuid")
        status = await service.get_session_status(session_id, session)
        cookies = await service.capture_cookies(session_id, session)
        await service.cleanup_session(session_id, session)
        ```

    Since:
        1.0.0
    """

    FANTRAX_LOGIN_URL = "https://www.fantrax.com/login"
    FANTRAX_HOME_URL = "https://www.fantrax.com/fantasy"

    async def create_auth_session(
        self,
        user_id: int,
        session_id: str
    ) -> Dict:
        """
        Create a new Selenium browser session for authentication.

        Initializes headless Chrome browser and prepares for Fantrax login.

        Args:
            user_id: ID of the user initiating authentication
            session_id: Unique session identifier

        Returns:
            Dictionary containing driver instance and process ID

        Raises:
            Exception: If Selenium initialization fails

        Performance:
            - Browser startup: 3-10 seconds
            - Memory footprint: ~400-600MB per session

        Since:
            1.0.0
        """
        try:
            logger.info(f"Creating Selenium session {session_id} for user {user_id}")

            # Configure Chrome options
            chrome_options = Options()
            chrome_options.add_argument("--headless")  # Run without GUI
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)

            # User agent to avoid bot detection
            chrome_options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )

            # Initialize Chrome driver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)

            # Get process ID for tracking
            try:
                pid = driver.service.process.pid
            except:
                pid = None

            logger.info(f"Selenium driver initialized for session {session_id} (PID: {pid})")

            return {
                "driver": driver,
                "pid": pid,
                "session_id": session_id,
                "user_id": user_id
            }

        except Exception as e:
            logger.error(f"Failed to create Selenium session: {str(e)}", exc_info=True)
            raise

    async def navigate_to_login(
        self,
        session_id: str,
        session: Dict
    ) -> None:
        """
        Navigate browser to Fantrax login page.

        Initiates navigation and updates session status when page loads.

        Args:
            session_id: Session identifier
            session: Session dictionary containing driver

        Raises:
            Exception: If navigation fails

        Performance:
            - Page load time: 2-5 seconds

        Since:
            1.0.0
        """
        try:
            driver = session["driver"]
            logger.info(f"Navigating session {session_id} to Fantrax login")

            # Navigate to login page (non-blocking)
            await asyncio.get_event_loop().run_in_executor(
                None,
                driver.get,
                self.FANTRAX_LOGIN_URL
            )

            # Update session status
            session["status"] = "ready"
            session["current_url"] = driver.current_url

            logger.info(f"Session {session_id} ready at {driver.current_url}")

        except Exception as e:
            logger.error(f"Failed to navigate session {session_id}: {str(e)}", exc_info=True)
            session["status"] = "failed"
            raise

    async def get_session_status(
        self,
        session_id: str,
        session: Dict
    ) -> Dict:
        """
        Get current status of authentication session.

        Checks browser state and determines if user has logged in.

        Args:
            session_id: Session identifier
            session: Session dictionary containing driver

        Returns:
            Dictionary with status and current URL

        Since:
            1.0.0
        """
        try:
            driver = session["driver"]
            current_url = driver.current_url

            # Determine status based on URL
            if "login" in current_url.lower():
                status = "ready"  # Still on login page
            elif "fantrax.com" in current_url and "login" not in current_url.lower():
                # User has logged in (redirected away from login)
                status = "authenticating"  # Ready to capture cookies
                logger.info(f"Session {session_id} detected successful login")
            else:
                status = session.get("status", "initializing")

            return {
                "status": status,
                "current_url": current_url
            }

        except Exception as e:
            logger.error(f"Failed to get status for session {session_id}: {str(e)}", exc_info=True)
            return {
                "status": "failed",
                "current_url": None
            }

    async def capture_cookies(
        self,
        session_id: str,
        session: Dict
    ) -> Optional[List[Dict]]:
        """
        Capture cookies from authenticated browser session.

        Extracts all cookies after successful Fantrax login.

        Args:
            session_id: Session identifier
            session: Session dictionary containing driver

        Returns:
            List of cookie dictionaries, or None if no cookies found

        Performance:
            - Cookie extraction: <1 second

        Since:
            1.0.0
        """
        try:
            driver = session["driver"]
            logger.info(f"Capturing cookies for session {session_id}")

            # Get all cookies
            cookies = driver.get_cookies()

            if not cookies:
                logger.warning(f"No cookies found for session {session_id}")
                return None

            # Filter for Fantrax-specific cookies
            fantrax_cookies = [
                cookie for cookie in cookies
                if "fantrax" in cookie.get("domain", "").lower()
            ]

            logger.info(f"Captured {len(fantrax_cookies)} Fantrax cookies for session {session_id}")

            return fantrax_cookies if fantrax_cookies else cookies

        except Exception as e:
            logger.error(f"Failed to capture cookies for session {session_id}: {str(e)}", exc_info=True)
            return None

    async def store_user_cookies(
        self,
        db: AsyncSession,
        user_id: int,
        cookies: List[Dict]
    ) -> bool:
        """
        Store encrypted cookies in user database record.

        Encrypts cookie data and updates user's Fantrax connection status.

        Args:
            db: Database session
            user_id: User ID to store cookies for
            cookies: List of cookie dictionaries from browser

        Returns:
            True if successful, False otherwise

        Security:
            - Cookies encrypted with AES-256 before storage
            - Encryption key stored in environment variables

        Since:
            1.0.0
        """
        try:
            logger.info(f"Storing encrypted cookies for user {user_id}")

            # Serialize cookies
            cookies_bytes = pickle.dumps(cookies)

            # Encrypt cookies
            encrypted_cookies = encrypt_value(cookies_bytes.decode("latin1"))

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

            logger.info(f"Successfully stored encrypted cookies for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store cookies for user {user_id}: {str(e)}", exc_info=True)
            await db.rollback()
            return False

    async def cleanup_session(
        self,
        session_id: str,
        session: Dict
    ) -> None:
        """
        Clean up Selenium browser session and release resources.

        Terminates browser process and frees memory. Should be called
        on success, failure, timeout, or cancellation.

        Args:
            session_id: Session identifier
            session: Session dictionary containing driver

        Performance:
            - Cleanup time: 1-3 seconds
            - Memory freed: ~400-600MB

        Since:
            1.0.0
        """
        try:
            driver = session.get("driver")
            if not driver:
                return

            logger.info(f"Cleaning up session {session_id}")

            # Quit browser
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    driver.quit
                )
            except Exception as e:
                logger.warning(f"Driver quit failed for session {session_id}: {str(e)}")

            # Attempt to kill process if still running
            pid = session.get("pid")
            if pid:
                try:
                    import psutil
                    if psutil.pid_exists(pid):
                        process = psutil.Process(pid)
                        process.terminate()
                        process.wait(timeout=5)
                        logger.info(f"Terminated browser process {pid} for session {session_id}")
                except Exception as e:
                    logger.warning(f"Failed to terminate process {pid}: {str(e)}")

            logger.info(f"Session {session_id} cleaned up successfully")

        except Exception as e:
            logger.error(f"Failed to cleanup session {session_id}: {str(e)}", exc_info=True)

    async def cleanup_expired_sessions(
        self,
        active_sessions: Dict[str, Dict]
    ) -> None:
        """
        Clean up all expired authentication sessions.

        Background task that runs periodically to remove orphaned sessions.

        Args:
            active_sessions: Dictionary of all active sessions

        Performance:
            - Should run every 5 minutes
            - Cleanup time: <10 seconds for all sessions

        Since:
            1.0.0
        """
        try:
            now = datetime.utcnow()
            expired_sessions = []

            # Find expired sessions
            for session_id, session in active_sessions.items():
                if now > session.get("expires_at", now):
                    expired_sessions.append(session_id)

            # Cleanup each expired session
            for session_id in expired_sessions:
                try:
                    session = active_sessions[session_id]
                    await self.cleanup_session(session_id, session)
                    del active_sessions[session_id]
                    logger.info(f"Cleaned up expired session {session_id}")
                except Exception as e:
                    logger.error(f"Failed to cleanup expired session {session_id}: {str(e)}")

            if expired_sessions:
                logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {str(e)}", exc_info=True)
