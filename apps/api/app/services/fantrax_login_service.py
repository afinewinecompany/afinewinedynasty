"""
Fantrax Username/Password Login Service

Handles direct authentication to Fantrax using username and password.
Captures session cookies for subsequent API requests.
"""

import logging
import httpx
from typing import Optional, Dict, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.db.models import User
from app.core.security import encrypt_value, decrypt_value
import json

logger = logging.getLogger(__name__)


class FantraxLoginService:
    """Service for authenticating users to Fantrax and storing session cookies"""

    FANTRAX_LOGIN_URL = "https://www.fantrax.com/login"
    # This endpoint handles the login form submission
    FANTRAX_AUTH_ENDPOINT = "https://www.fantrax.com/newui/login/doLogin.go"

    @staticmethod
    async def authenticate_user(
        email: str,
        password: str,
        db: AsyncSession,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Authenticate user with Fantrax using email/password.

        Performs server-side login to Fantrax, captures session cookies,
        encrypts and stores them in the database.

        Args:
            email: Fantrax account email
            password: Fantrax account password
            db: Database session
            user_id: Current user's ID

        Returns:
            Dict with success status and message/error

        Example:
            ```python
            result = await FantraxLoginService.authenticate_user(
                email="user@example.com",
                password="password123",
                db=db,
                user_id=1
            )
            if result["success"]:
                print("Logged in successfully!")
            ```
        """
        try:
            logger.info(f"Attempting Fantrax login for user {user_id}")

            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                # Step 1: Get the login page to capture any CSRF tokens/cookies
                logger.info("Fetching Fantrax login page...")
                response = await client.get(FantraxLoginService.FANTRAX_LOGIN_URL)

                if response.status_code != 200:
                    logger.error(f"Failed to load login page: {response.status_code}")
                    return {
                        "success": False,
                        "error": f"Failed to load Fantrax login page (HTTP {response.status_code})"
                    }

                # Step 2: Submit login credentials as form data (not JSON)
                logger.info("Submitting login credentials...")
                login_data = {
                    "username": email,  # Fantrax uses 'username' not 'email'
                    "password": password,
                    "remember": "on"  # Remember me checkbox
                }

                # Submit as form data (application/x-www-form-urlencoded)
                auth_response = await client.post(
                    FantraxLoginService.FANTRAX_AUTH_ENDPOINT,
                    data=login_data,  # Use 'data' for form encoding, not 'json'
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Referer": FantraxLoginService.FANTRAX_LOGIN_URL,
                        "Origin": "https://www.fantrax.com"
                    }
                )

                logger.info(f"Auth response status: {auth_response.status_code}")
                logger.info(f"Auth response URL: {auth_response.url}")

                # Check if login was successful by checking:
                # 1. Status code (200 or 302 redirect)
                # 2. Cookies received
                # 3. No error in response

                cookies = client.cookies
                logger.info(f"Cookies after login: {len(cookies)} cookies")

                # Check if we got authentication cookies
                has_auth_cookie = any(
                    'fantrax' in name.lower() or 'session' in name.lower() or 'auth' in name.lower()
                    for name in cookies.keys()
                )

                # Check response for error indicators
                response_text = auth_response.text.lower()
                has_error = (
                    'error' in response_text or
                    'invalid' in response_text or
                    'incorrect' in response_text or
                    'failed' in response_text
                )

                if has_auth_cookie and not has_error:
                    # Login successful - extract cookies
                    if not cookies:
                        logger.warning("Login appeared successful but no cookies received")
                        return {
                            "success": False,
                            "error": "Authentication succeeded but no session cookies were received"
                        }

                    # Convert cookies to dictionary format
                    cookie_list = []
                    for name, value in cookies.items():
                        cookie_list.append({
                            "name": name,
                            "value": value,
                            "domain": ".fantrax.com"
                        })

                    logger.info(f"Captured {len(cookie_list)} cookies from Fantrax login")
                    logger.info(f"Cookie names: {[c['name'] for c in cookie_list]}")

                    # Encrypt and store cookies
                    cookies_json = json.dumps(cookie_list)
                    encrypted_cookies = encrypt_value(cookies_json)

                    # Update user record
                    stmt = (
                        update(User)
                        .where(User.id == user_id)
                        .values(fantrax_cookies=encrypted_cookies)
                    )
                    await db.execute(stmt)
                    await db.commit()

                    logger.info(f"Successfully stored Fantrax cookies for user {user_id}")

                    return {
                        "success": True,
                        "message": "Successfully connected to Fantrax!",
                        "cookie_count": len(cookie_list)
                    }
                else:
                    # Login failed
                    logger.warning(f"Fantrax login failed - has_auth_cookie: {has_auth_cookie}, has_error: {has_error}")
                    logger.warning(f"Response excerpt: {auth_response.text[:500]}")

                    error_msg = "Invalid Fantrax credentials"
                    if 'email' in response_text and 'password' in response_text:
                        error_msg = "Please check your email and password"

                    return {
                        "success": False,
                        "error": error_msg
                    }

        except httpx.TimeoutException:
            logger.error("Fantrax login request timed out")
            return {
                "success": False,
                "error": "Connection to Fantrax timed out. Please try again."
            }
        except Exception as e:
            logger.error(f"Fantrax login error: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to connect to Fantrax: {str(e)}"
            }
