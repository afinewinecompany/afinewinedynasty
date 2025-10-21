"""
Clear composite rankings cache to force regeneration with new pitch data.
"""

import asyncio
from app.core.cache_manager import cache_manager


async def clear_cache():
    """Clear all composite rankings cache keys."""
    print("Clearing composite rankings cache...")

    # Initialize cache manager
    await cache_manager.initialize()

    # Common cache key patterns
    patterns = [
        "composite_rankings:free:*",
        "composite_rankings:premium:*",
    ]

    total_cleared = 0
    for pattern in patterns:
        try:
            # Find all keys matching pattern
            keys = await cache_manager.redis_client.keys(pattern)

            if keys:
                # Delete all matching keys
                await cache_manager.redis_client.delete(*keys)
                total_cleared += len(keys)
                print(f"  Cleared {len(keys)} keys matching: {pattern}")
            else:
                print(f"  No keys found matching: {pattern}")

        except Exception as e:
            print(f"  Error clearing pattern {pattern}: {e}")

    # Close cache manager connection
    await cache_manager.close()

    print(f"\nCache cleared! ({total_cleared} total keys)")
    print("Next API request will regenerate rankings with pitch data.")


if __name__ == "__main__":
    asyncio.run(clear_cache())
