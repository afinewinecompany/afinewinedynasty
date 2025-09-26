"""Rate limiting for ML prediction endpoints."""

import time
from typing import Dict, Optional
import asyncio

from fastapi import HTTPException


class RateLimiter:
    """Simple in-memory rate limiter for ML prediction endpoints."""

    def __init__(self, requests_per_minute: int, identifier: str = "default"):
        self.requests_per_minute = requests_per_minute
        self.identifier = identifier
        self.requests: Dict[str, list] = {}
        self.lock = asyncio.Lock()

    async def check_rate_limit(self, user_id: int):
        """Check if user has exceeded rate limit."""
        async with self.lock:
            current_time = time.time()
            user_key = f"{self.identifier}_{user_id}"

            # Initialize or clean old requests
            if user_key not in self.requests:
                self.requests[user_key] = []

            # Remove requests older than 1 minute
            self.requests[user_key] = [
                req_time for req_time in self.requests[user_key]
                if current_time - req_time < 60
            ]

            # Check if limit exceeded
            if len(self.requests[user_key]) >= self.requests_per_minute:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {self.requests_per_minute} requests per minute"
                )

            # Add current request
            self.requests[user_key].append(current_time)