"""
Fantrax Playwright Authentication Service

Handles browser automation using Playwright for Fantrax authentication.
More reliable than Selenium in containerized environments.

@module fantrax_playwright_service
@since 1.1.0
"""

import logging
import asyncio
import json
from typing import Optional, Dict, List
from datetime import datetime

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from app.db.models import User
from app.core.security import encrypt_value

logger = logging.getLogger(__name__)


class FantraxPlaywrightService:
    """
    Service for managing Fantrax authentication via Playwright.

    Playwright is more reliable than Selenium in containerized environments
    and handles Cloudflare protection better.

    Example:
        ```python
        service = FantraxPlaywrightService()
        session = await service.create_auth_session(user_id=1, session_id="uuid")
        status = await service.get_session_status(session_id, session)
        cookies = await service.capture_cookies(session_id, session)
        await service.cleanup_session(session_id, session)
        ```

    Since:
        1.1.0
    """

    FANTRAX_LOGIN_URL = "https://www.fantrax.com/login"
    FANTRAX_HOME_URL = "https://www.fantrax.com/fantasy"

    async def create_auth_session(
        self,
        user_id: int,
        session_id: str
    ) -> Dict:
        """
        Create a new Playwright browser session for authentication.

        Initializes headless Chromium browser and prepares for Fantrax login.

        Args:
            user_id: ID of the user initiating authentication
            session_id: Unique session identifier

        Returns:
            Dictionary containing playwright instance, browser, context, and page

        Raises:
            Exception: If Playwright initialization fails

        Performance:
            - Browser startup: 2-5 seconds (faster than Selenium)
            - Memory footprint: ~300-400MB per session (lighter than Selenium)

        Since:
            1.1.0
        """
        try:
            logger.info(f"Creating Playwright session {session_id} for user {user_id}")

            # Start Playwright
            playwright = await async_playwright().start()

            # Launch browser with container-optimized flags
            try:
                browser = await playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--no-first-run',
                        '--no-zygote',
                        '--single-process',  # Critical for containers
                        '--disable-gpu',
                    ]
                )
            except Exception as browser_error:
                logger.error(f"Browser launch failed: {str(browser_error)}")
                await playwright.stop()
                raise RuntimeError(
                    "Failed to launch Playwright browser. "
                    "This may indicate Chromium is not installed correctly. "
                    "Please ensure 'playwright install chromium --with-deps' was run during deployment. "
                    f"Error: {str(browser_error)}"
                )

            # Create browser context with realistic settings
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/New_York',
            )

            # Create page
            page = await context.new_page()

            logger.info(f"Playwright session {session_id} initialized successfully")

            return {
                "playwright": playwright,
                "browser": browser,
                "context": context,
                "page": page,
                "session_id": session_id,
                "user_id": user_id
            }

        except Exception as e:
            logger.error(f"Failed to create Playwright session: {str(e)}", exc_info=True)
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
            session: Session dictionary containing page

        Raises:
            Exception: If navigation fails

        Performance:
            - Page load time: 1-3 seconds
            - Playwright auto-waits for network idle

        Since:
            1.1.0
        """
        try:
            page: Page = session["page"]
            logger.info(f"Navigating session {session_id} to Fantrax login")

            # Navigate to login page
            # Use 'domcontentloaded' instead of 'networkidle' for faster loading
            # with Cloudflare-protected sites
            await page.goto(
                self.FANTRAX_LOGIN_URL,
                wait_until='domcontentloaded',  # Wait for DOM to be ready (faster than networkidle)
                timeout=60000  # 60 second timeout for Cloudflare challenge
            )

            # Wait a bit for any Cloudflare challenges to resolve
            await asyncio.sleep(2)

            # Update session status
            session["status"] = "ready"
            session["current_url"] = page.url

            logger.info(f"Session {session_id} ready at {page.url}")

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
            session: Session dictionary containing page

        Returns:
            Dictionary with status and current URL

        Since:
            1.1.0
        """
        try:
            page: Page = session["page"]
            current_url = page.url

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
            session: Session dictionary containing context

        Returns:
            List of cookie dictionaries, or None if no cookies found

        Performance:
            - Cookie extraction: <500ms (faster than Selenium)

        Since:
            1.1.0
        """
        try:
            context: BrowserContext = session["context"]
            logger.info(f"Capturing cookies for session {session_id}")

            # Get all cookies from context
            cookies = await context.cookies()

            if not cookies:
                logger.warning(f"No cookies found for session {session_id}")
                return None

            # Filter for Fantrax-specific cookies
            fantrax_cookies = [
                {
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": cookie.get("domain", ".fantrax.com"),
                    "path": cookie.get("path", "/"),
                    "expires": cookie.get("expires", -1),
                    "httpOnly": cookie.get("httpOnly", False),
                    "secure": cookie.get("secure", True),
                    "sameSite": cookie.get("sameSite", "Lax")
                }
                for cookie in cookies
                if "fantrax" in cookie.get("domain", "").lower()
            ]

            logger.info(f"Captured {len(fantrax_cookies)} Fantrax cookies for session {session_id}")
            logger.debug(f"Cookie names: {[c['name'] for c in fantrax_cookies]}")

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
            1.1.0
        """
        try:
            logger.info(f"Storing encrypted cookies for user {user_id}")

            # Serialize cookies to JSON
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
        Clean up Playwright browser session and release resources.

        Closes browser, context, and playwright instance. Should be called
        on success, failure, timeout, or cancellation.

        Args:
            session_id: Session identifier
            session: Session dictionary containing playwright objects

        Performance:
            - Cleanup time: <1 second (faster than Selenium)
            - Memory freed: ~300-400MB

        Since:
            1.1.0
        """
        try:
            logger.info(f"Cleaning up Playwright session {session_id}")

            # Close page
            page: Optional[Page] = session.get("page")
            if page and not page.is_closed():
                await page.close()

            # Close context
            context: Optional[BrowserContext] = session.get("context")
            if context:
                await context.close()

            # Close browser
            browser: Optional[Browser] = session.get("browser")
            if browser and browser.is_connected():
                await browser.close()

            # Stop playwright
            playwright: Optional[Playwright] = session.get("playwright")
            if playwright:
                await playwright.stop()

            logger.info(f"Session {session_id} cleaned up successfully")

        except Exception as e:
            logger.error(f"Failed to cleanup session {session_id}: {str(e)}", exc_info=True)

    async def wait_for_login(
        self,
        session_id: str,
        session: Dict,
        timeout: int = 90
    ) -> bool:
        """
        Wait for user to complete login in browser.

        Polls page URL until user is redirected away from login page.

        Args:
            session_id: Session identifier
            session: Session dictionary containing page
            timeout: Maximum seconds to wait

        Returns:
            True if login detected, False if timeout

        Performance:
            - Polls every 2 seconds
            - Maximum wait: timeout seconds

        Since:
            1.1.0
        """
        try:
            page: Page = session["page"]
            start_time = datetime.utcnow()

            while (datetime.utcnow() - start_time).total_seconds() < timeout:
                current_url = page.url

                # Check if redirected away from login
                if "login" not in current_url.lower() and "fantrax.com" in current_url:
                    logger.info(f"Session {session_id} login detected at {current_url}")
                    return True

                # Wait 2 seconds before checking again
                await asyncio.sleep(2)

            logger.warning(f"Session {session_id} timed out waiting for login")
            return False

        except Exception as e:
            logger.error(f"Error waiting for login on session {session_id}: {str(e)}", exc_info=True)
            return False
