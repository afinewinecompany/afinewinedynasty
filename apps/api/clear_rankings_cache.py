"""
Clear composite rankings cache to force regeneration with new pitch data.
"""

import asyncio
from app.services.cache_manager import cache_manager


async def clear_cache():
    """Clear all composite rankings cache keys."""
    print("Clearing composite rankings cache...")

    # Common cache key patterns
    patterns = [
        "composite_rankings:free:*",
        "composite_rankings:premium:*",
    ]

    cleared = 0
    for pattern in patterns:
        try:
            # Clear by pattern (if Redis supports it)
            await cache_manager.delete_pattern(pattern)
            cleared += 1
            print(f"  Cleared: {pattern}")
        except AttributeError:
            # Fallback: clear specific known keys
            keys_to_clear = [
                "composite_rankings:free:None:None:None",
                "composite_rankings:premium:None:None:None",
            ]
            for key in keys_to_clear:
                try:
                    await cache_manager.redis.delete(key)
                    print(f"  Cleared: {key}")
                    cleared += 1
                except Exception as e:
                    print(f"  Could not clear {key}: {e}")

    print(f"\nCache cleared! ({cleared} operations)")
    print("Next API request will regenerate rankings with pitch data.")


if __name__ == "__main__":
    asyncio.run(clear_cache())
