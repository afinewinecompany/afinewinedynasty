"""Prospect search service with fuzzy matching."""

from typing import List, Optional
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Prospect
from app.core.config import settings


class ProspectSearchService:
    """Service for searching prospects with fuzzy matching."""

    @staticmethod
    async def search_prospects(
        db: AsyncSession,
        search_query: str,
        limit: int = 10
    ) -> List[Prospect]:
        """
        Search for prospects using fuzzy matching on names and organizations.

        Uses PostgreSQL's similarity functions for fuzzy matching.
        Falls back to ILIKE if similarity extensions are not available.

        Args:
            db: Database session
            search_query: Search string
            limit: Maximum number of results to return

        Returns:
            List of matching prospects
        """
        if not search_query or len(search_query.strip()) < 2:
            return []

        search_term = search_query.strip().lower()

        # Try using PostgreSQL similarity search (requires pg_trgm extension)
        try:
            # First try exact match, then fuzzy match
            query = select(Prospect).where(
                or_(
                    func.lower(Prospect.name).contains(search_term),
                    func.lower(Prospect.organization).contains(search_term),
                    func.similarity(Prospect.name, search_query) > 0.3,
                    func.similarity(Prospect.organization, search_query) > 0.3
                )
            ).order_by(
                # Order by relevance
                func.greatest(
                    func.similarity(Prospect.name, search_query),
                    func.similarity(Prospect.organization, search_query)
                ).desc()
            ).limit(limit)

            result = await db.execute(query)
            return result.scalars().all()

        except Exception:
            # Fallback to ILIKE if pg_trgm is not installed
            pattern = f"%{search_term}%"
            query = select(Prospect).where(
                or_(
                    Prospect.name.ilike(pattern),
                    Prospect.organization.ilike(pattern)
                )
            ).limit(limit)

            result = await db.execute(query)
            return result.scalars().all()

    @staticmethod
    async def search_prospects_autocomplete(
        db: AsyncSession,
        prefix: str,
        limit: int = 5
    ) -> List[dict]:
        """
        Get autocomplete suggestions for prospect names.

        Args:
            db: Database session
            prefix: Search prefix
            limit: Maximum number of suggestions

        Returns:
            List of suggestion dictionaries with name and organization
        """
        if not prefix or len(prefix.strip()) < 1:
            return []

        search_term = prefix.strip().lower()
        pattern = f"{search_term}%"

        # Search for prospects whose names start with the prefix
        query = select(
            Prospect.name,
            Prospect.organization,
            Prospect.position
        ).where(
            func.lower(Prospect.name).like(pattern)
        ).order_by(
            Prospect.name
        ).limit(limit)

        result = await db.execute(query)
        prospects = result.all()

        return [
            {
                'name': p.name,
                'organization': p.organization,
                'position': p.position,
                'display': f"{p.name} ({p.position}, {p.organization})"
            }
            for p in prospects
        ]