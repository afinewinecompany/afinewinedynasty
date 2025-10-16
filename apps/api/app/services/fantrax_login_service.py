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
    FANTRAX_AUTH_ENDPOINT = "https://www.fantrax.com/fxpa/req?leagueId=ALL"

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

                # Step 2: Submit login credentials
                logger.info("Submitting login credentials...")
                login_data = {
                    "email": email,
                    "password": password,
                    "rememberMe": "true"
                }

                # Try the authentication endpoint
                auth_response = await client.post(
                    FantraxLoginService.FANTRAX_AUTH_ENDPOINT,
                    json=login_data,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Referer": FantraxLoginService.FANTRAX_LOGIN_URL
                    }
                )

                logger.info(f"Auth response status: {auth_response.status_code}")

                # Check if login was successful
                # Fantrax returns JSON response with success indicator
                try:
                    auth_json = auth_response.json()
                    logger.info(f"Auth response: {auth_json}")

                    # Check various success indicators
                    if auth_json.get("success") or auth_json.get("status") == "success":
                        # Login successful - extract cookies
                        cookies = client.cookies

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
                        error_msg = auth_json.get("message") or auth_json.get("error") or "Invalid credentials"
                        logger.warning(f"Fantrax login failed: {error_msg}")
                        return {
                            "success": False,
                            "error": f"Fantrax login failed: {error_msg}"
                        }

                except ValueError as e:
                    logger.error(f"Failed to parse auth response as JSON: {e}")
                    logger.error(f"Response text: {auth_response.text[:500]}")

                    # Check if we got cookies anyway (some endpoints don't return JSON on success)
                    cookies = client.cookies
                    if cookies and len(cookies) > 0:
                        cookie_list = []
                        for name, value in cookies.items():
                            cookie_list.append({
                                "name": name,
                                "value": value,
                                "domain": ".fantrax.com"
                            })

                        # Store cookies
                        cookies_json = json.dumps(cookie_list)
                        encrypted_cookies = encrypt_value(cookies_json)

                        stmt = (
                            update(User)
                            .where(User.id == user_id)
                            .values(fantrax_cookies=encrypted_cookies)
                        )
                        await db.execute(stmt)
                        await db.commit()

                        return {
                            "success": True,
                            "message": "Successfully connected to Fantrax!",
                            "cookie_count": len(cookie_list)
                        }

                    return {
                        "success": False,
                        "error": "Unexpected response from Fantrax login"
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
