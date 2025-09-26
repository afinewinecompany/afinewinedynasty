"""Fangraphs data scraping service with rate limiting."""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import quote

import aiohttp
from bs4 import BeautifulSoup
from fastapi import HTTPException

from app.core.config import settings
from app.core.rate_limiting import RateLimiter
from app.core.circuit_breaker import circuit_breaker_registry, CircuitBreakerException
from app.services.pipeline_monitoring import PipelineMonitor

logger = logging.getLogger(__name__)


class FangraphsRateLimiter:
    """Rate limiter specifically for Fangraphs API calls (1 req/sec)."""

    def __init__(self, calls: int = 1, period: float = 1.0):
        self.calls = calls
        self.period = period
        self.last_call = 0.0
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        async with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_call

            if time_since_last < self.period:
                sleep_time = self.period - time_since_last
                await asyncio.sleep(sleep_time)

            self.last_call = time.time()
            return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class FangraphsService:
    """Service for scraping Fangraphs prospect data."""

    BASE_URL = "https://www.fangraphs.com"
    USER_AGENT = "A Fine Wine Dynasty Bot 1.0 (Responsible Scraping)"

    def __init__(self):
        self.rate_limiter = FangraphsRateLimiter(calls=1, period=1.0)
        self.session: Optional[aiohttp.ClientSession] = None
        self.monitor = PipelineMonitor()
        self.retry_count = 3
        self.retry_delay = 2.0
        self._connection_pool_size = 10
        self._connection_timeout = 30

        # Initialize circuit breaker
        self.circuit_breaker = circuit_breaker_registry.register(
            name="fangraphs_service",
            failure_threshold=5,
            recovery_timeout=300,  # 5 minutes
            expected_exception=(aiohttp.ClientError, asyncio.TimeoutError, HTTPException),
            success_threshold=3
        )

    async def __aenter__(self):
        """Initialize session with connection pooling."""
        connector = aiohttp.TCPConnector(
            limit=self._connection_pool_size,
            limit_per_host=5,
            ttl_dns_cache=300
        )

        timeout = aiohttp.ClientTimeout(
            total=self._connection_timeout,
            connect=10,
            sock_connect=10,
            sock_read=20
        )

        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0"
            }
        )

        logger.info("Fangraphs service session initialized with connection pooling")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close session properly."""
        if self.session:
            await self.session.close()
            # Allow time for connections to close properly
            await asyncio.sleep(0.25)

    async def _make_request(self, url: str, retry_attempt: int = 0) -> Optional[str]:
        """Make HTTP request with rate limiting, error handling, and retry logic."""
        try:
            # Check circuit breaker state before making request
            if self.circuit_breaker.is_open():
                logger.warning(f"Circuit breaker is OPEN for FanGraphs service, skipping request to {url}")
                await self.monitor.record_fetch_error("fangraphs", url, "Circuit breaker is open")
                return None

            async with self.rate_limiter:
                logger.debug(f"Making request to: {url} (attempt {retry_attempt + 1})")

                # Wrap the request in circuit breaker protection
                response_content = await self.circuit_breaker.call(self._execute_request, url)
                return response_content

        except CircuitBreakerException as e:
            logger.error(f"Circuit breaker prevented request to {url}: {str(e)}")
            await self.monitor.record_fetch_error("fangraphs", url, f"Circuit breaker: {str(e)}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error in _make_request for {url}: {str(e)}")
            await self.monitor.record_fetch_error("fangraphs", url, f"Unexpected: {str(e)}")
            return None

    async def _execute_request(self, url: str) -> Optional[str]:
        """Execute the actual HTTP request (protected by circuit breaker)."""
        async with self.session.get(url) as response:
            if response.status == 200:
                content = await response.text()
                logger.info(f"Successfully fetched data from: {url}")
                await self.monitor.record_successful_fetch("fangraphs", url)
                return content

            elif response.status == 429:  # Rate limited
                logger.warning(f"Rate limited by Fangraphs (429). Backing off...")
                await self.monitor.record_rate_limit_hit("fangraphs")
                raise HTTPException(
                    status_code=429,
                    detail="Fangraphs rate limit exceeded"
                )

            elif response.status == 404:
                logger.warning(f"Page not found: {url}")
                await self.monitor.record_fetch_error("fangraphs", url, "404 Not Found")
                return None

            else:
                error_msg = f"HTTP {response.status}: {response.reason}"
                logger.error(f"Request failed: {error_msg} for {url}")
                await self.monitor.record_fetch_error("fangraphs", url, error_msg)
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=error_msg
                )

    async def get_prospect_data(self, prospect_name: str) -> Optional[Dict[str, Any]]:
        """Fetch prospect data from Fangraphs."""
        try:
            # Format prospect name for URL
            url_name = quote(prospect_name.lower().replace(" ", "-"))
            url = f"{self.BASE_URL}/prospects/{url_name}"

            html_content = await self._make_request(url)
            if not html_content:
                return None

            # Parse HTML and extract data
            return self._parse_prospect_data(html_content, prospect_name)

        except Exception as e:
            logger.error(f"Error getting prospect data for {prospect_name}: {str(e)}")
            await self.monitor.record_processing_error("fangraphs", f"prospect_{prospect_name}", str(e))
            return None

    def _parse_prospect_data(self, html: str, prospect_name: str) -> Dict[str, Any]:
        """Parse prospect data from HTML content."""
        try:
            soup = BeautifulSoup(html, 'html.parser')

            data = {
                "name": prospect_name,
                "source": "fangraphs",
                "fetched_at": datetime.utcnow().isoformat(),
                "scouting_grades": {},
                "statistics": {},
                "rankings": {},
                "bio": {}
            }

            # Extract scouting grades (20-80 scale)
            grades_section = soup.find('div', {'class': 'prospects-grades'})
            if grades_section:
                for grade_item in grades_section.find_all('div', {'class': 'grade-item'}):
                    skill_name = grade_item.find('span', {'class': 'skill-name'})
                    skill_grade = grade_item.find('span', {'class': 'grade-value'})

                    if skill_name and skill_grade:
                        skill = skill_name.text.strip().lower().replace(' ', '_')
                        try:
                            grade = int(skill_grade.text.strip())
                            data["scouting_grades"][skill] = grade
                        except ValueError:
                            logger.warning(f"Could not parse grade for {skill}: {skill_grade.text}")

            # Extract statistics
            stats_table = soup.find('table', {'class': 'prospects-stats'})
            if stats_table:
                headers = [th.text.strip() for th in stats_table.find_all('th')]
                for row in stats_table.find_all('tr')[1:]:  # Skip header row
                    cells = row.find_all('td')
                    if cells and len(cells) == len(headers):
                        year = cells[0].text.strip()
                        if year not in data["statistics"]:
                            data["statistics"][year] = {}

                        for i, header in enumerate(headers[1:], 1):
                            value = cells[i].text.strip()
                            try:
                                # Try to convert to number if possible
                                if '.' in value:
                                    data["statistics"][year][header] = float(value)
                                else:
                                    data["statistics"][year][header] = int(value)
                            except ValueError:
                                data["statistics"][year][header] = value

            # Extract rankings
            rankings_section = soup.find('div', {'class': 'prospect-rankings'})
            if rankings_section:
                rank_items = rankings_section.find_all('span', {'class': 'rank-item'})
                for item in rank_items:
                    rank_text = item.text.strip()
                    if '#' in rank_text:
                        parts = rank_text.split('#')
                        if len(parts) == 2:
                            rank_type = parts[0].strip()
                            rank_value = parts[1].strip()
                            try:
                                data["rankings"][rank_type] = int(rank_value)
                            except ValueError:
                                data["rankings"][rank_type] = rank_value

            # Extract bio information
            bio_section = soup.find('div', {'class': 'prospect-bio'})
            if bio_section:
                for info_item in bio_section.find_all('div', {'class': 'bio-item'}):
                    label = info_item.find('span', {'class': 'bio-label'})
                    value = info_item.find('span', {'class': 'bio-value'})

                    if label and value:
                        key = label.text.strip().lower().replace(' ', '_').rstrip(':')
                        data["bio"][key] = value.text.strip()

            logger.info(f"Successfully parsed data for {prospect_name}")
            return data

        except Exception as e:
            logger.error(f"Error parsing prospect data: {str(e)}")
            raise

    async def get_top_prospects_list(self, year: int = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch list of top prospects from Fangraphs."""
        try:
            year = year or datetime.now().year
            url = f"{self.BASE_URL}/prospects-list/{year}"

            html_content = await self._make_request(url)
            if not html_content:
                return []

            return self._parse_prospects_list(html_content, limit)

        except Exception as e:
            logger.error(f"Error getting top prospects list: {str(e)}")
            await self.monitor.record_processing_error("fangraphs", "top_prospects_list", str(e))
            return []

    def _parse_prospects_list(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse prospects list from HTML content."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            prospects = []

            # Find prospects table
            table = soup.find('table', {'class': 'prospects-list'})
            if not table:
                logger.warning("Could not find prospects list table")
                return []

            for row in table.find_all('tr')[1:limit+1]:  # Skip header, limit results
                cells = row.find_all('td')
                if len(cells) >= 5:  # Expecting rank, name, org, position, eta
                    prospect = {
                        "rank": cells[0].text.strip(),
                        "name": cells[1].text.strip(),
                        "organization": cells[2].text.strip(),
                        "position": cells[3].text.strip(),
                        "eta": cells[4].text.strip() if len(cells) > 4 else None
                    }

                    # Extract link to prospect page if available
                    name_link = cells[1].find('a')
                    if name_link and 'href' in name_link.attrs:
                        prospect["profile_url"] = name_link['href']

                    prospects.append(prospect)

            logger.info(f"Successfully parsed {len(prospects)} prospects from list")
            return prospects

        except Exception as e:
            logger.error(f"Error parsing prospects list: {str(e)}")
            return []

    async def batch_fetch_prospects(self, prospect_names: List[str]) -> List[Dict[str, Any]]:
        """Fetch multiple prospects with proper rate limiting."""
        results = []

        for name in prospect_names:
            logger.info(f"Fetching data for prospect: {name}")
            data = await self.get_prospect_data(name)

            if data:
                results.append(data)
            else:
                logger.warning(f"No data found for prospect: {name}")

            # Monitor progress
            await self.monitor.record_batch_progress("fangraphs", len(results), len(prospect_names))

        logger.info(f"Batch fetch complete: {len(results)}/{len(prospect_names)} prospects fetched")
        return results

    def get_service_health(self) -> Dict[str, Any]:
        """Get service health including circuit breaker status."""
        return {
            "service": "fangraphs",
            "circuit_breaker": self.circuit_breaker.get_metrics(),
            "session_active": self.session is not None,
            "rate_limiter": {
                "calls": self.rate_limiter.calls,
                "period": self.rate_limiter.period,
                "last_call": self.rate_limiter.last_call
            }
        }

    async def reset_circuit_breaker(self):
        """Manually reset the circuit breaker."""
        await self.circuit_breaker.reset()
        logger.info("FanGraphs service circuit breaker manually reset")