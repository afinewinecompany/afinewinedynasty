"""
Test script to verify HYPE social media API connections
Run this to confirm your API credentials are working
"""

import os
import sys
import asyncio
import aiohttp
from datetime import datetime
from dotenv import load_dotenv

# Fix Unicode output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load environment variables from the API directory
load_dotenv('apps/api/.env')


async def test_twitter_api():
    """Test Twitter/X API connection"""
    print("\n🐦 Testing Twitter/X API...")

    bearer_token = os.getenv('TWITTER_BEARER_TOKEN')

    if not bearer_token:
        print("❌ TWITTER_BEARER_TOKEN not found in environment variables")
        return False

    try:
        # Test with a simple search query
        search_url = "https://api.twitter.com/2/tweets/search/recent"

        params = {
            'query': 'baseball',
            'max_results': 10
        }

        headers = {
            'Authorization': f'Bearer {bearer_token}'
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    tweet_count = len(data.get('data', []))
                    print(f"✅ Twitter API working! Retrieved {tweet_count} tweets")
                    return True
                elif response.status == 401:
                    print("❌ Twitter API authentication failed - check your bearer token")
                elif response.status == 429:
                    print("⚠️  Twitter API rate limit reached - try again later")
                else:
                    print(f"❌ Twitter API error: Status {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                return False

    except Exception as e:
        print(f"❌ Twitter API connection error: {e}")
        return False


async def test_reddit_api():
    """Test Reddit API connection"""
    print("\n🤖 Testing Reddit API...")

    client_id = os.getenv('REDDIT_CLIENT_ID')
    client_secret = os.getenv('REDDIT_SECRET')

    if not client_id or not client_secret:
        print("❌ REDDIT_CLIENT_ID or REDDIT_SECRET not found in environment variables")
        return False

    try:
        # Get access token
        auth_url = "https://www.reddit.com/api/v1/access_token"

        auth = aiohttp.BasicAuth(client_id, client_secret)
        data = {'grant_type': 'client_credentials'}
        headers = {'User-Agent': 'AFineWineDynasty/1.0'}

        async with aiohttp.ClientSession() as session:
            # Get token
            async with session.post(auth_url, auth=auth, data=data, headers=headers) as response:
                if response.status != 200:
                    print(f"❌ Reddit authentication failed: Status {response.status}")
                    return False

                token_data = await response.json()
                access_token = token_data.get('access_token')

                if not access_token:
                    print("❌ Reddit authentication failed: No access token received")
                    return False

            # Test API with token
            test_url = "https://oauth.reddit.com/r/baseball/hot.json"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'User-Agent': 'AFineWineDynasty/1.0'
            }
            params = {'limit': 5}

            async with session.get(test_url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    post_count = len(data.get('data', {}).get('children', []))
                    print(f"✅ Reddit API working! Retrieved {post_count} posts from r/baseball")
                    return True
                else:
                    print(f"❌ Reddit API error: Status {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return False

    except Exception as e:
        print(f"❌ Reddit API connection error: {e}")
        return False


async def test_bluesky_api():
    """Test Bluesky API connection using the official AT Protocol SDK with authentication"""
    print("\n☁️ Testing Bluesky API (using official SDK with auth)...")

    bluesky_handle = os.getenv('BLUESKY_HANDLE')
    bluesky_password = os.getenv('BLUESKY_APP_PASSWORD')

    if not bluesky_handle or not bluesky_password:
        print("❌ BLUESKY_HANDLE or BLUESKY_APP_PASSWORD not found in environment variables")
        return False

    try:
        from atproto import Client as AtProtoClient
        from concurrent.futures import ThreadPoolExecutor

        # Create client
        client = AtProtoClient()

        # Execute in a thread pool since SDK is synchronous
        executor = ThreadPoolExecutor(max_workers=1)
        loop = asyncio.get_event_loop()

        # Authenticate
        try:
            await loop.run_in_executor(
                executor,
                lambda: client.login(bluesky_handle, bluesky_password)
            )
            print(f"   ✓ Authenticated as {bluesky_handle}")
        except Exception as auth_error:
            print(f"❌ Bluesky authentication failed: {auth_error}")
            return False

        # Search for posts
        response = await loop.run_in_executor(
            executor,
            lambda: client.app.bsky.feed.search_posts({'q': 'baseball', 'limit': 5})
        )

        post_count = len(response.posts)
        print(f"✅ Bluesky API working! Retrieved {post_count} posts")

        # Show sample post
        if response.posts:
            sample_post = response.posts[0]
            print(f"   Sample: @{sample_post.author.handle}: {sample_post.record.text[:60]}...")

        return True

    except Exception as e:
        error_msg = str(e)
        if '429' in error_msg:
            print("⚠️  Bluesky API rate limit reached - try again later")
        else:
            print(f"❌ Bluesky API connection error: {error_msg}")
        return False


async def test_hype_feature():
    """Test the complete HYPE feature setup"""
    print("\n" + "="*50)
    print("🚀 HYPE Feature API Test Suite")
    print("="*50)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Check environment
    env_file_exists = os.path.exists('.env')
    print(f"\n📁 .env file exists: {'✅ Yes' if env_file_exists else '❌ No'}")

    # Test APIs
    twitter_ok = await test_twitter_api()
    reddit_ok = await test_reddit_api()
    bluesky_ok = await test_bluesky_api()

    # Summary
    print("\n" + "="*50)
    print("📊 Test Results Summary:")
    print("="*50)

    results = [
        ("Twitter/X API", twitter_ok),
        ("Reddit API", reddit_ok),
        ("Bluesky API", bluesky_ok)
    ]

    for name, status in results:
        icon = "✅" if status else "❌"
        print(f"{icon} {name}: {'Working' if status else 'Failed'}")

    all_passed = all(status for _, status in results)

    print("\n" + "="*50)
    if all_passed:
        print("🎉 All tests passed! HYPE feature is ready to use!")
    elif any(status for _, status in results):
        print("⚠️  Some APIs are working. HYPE feature will work with limited data sources.")
    else:
        print("❌ No APIs are working. Please check your credentials.")

    print("\n💡 Next steps:")
    if not twitter_ok:
        print("   1. Get Twitter Bearer Token from https://developer.twitter.com/")
    if not reddit_ok:
        print("   2. Get Reddit credentials from https://www.reddit.com/prefs/apps")
    if all_passed:
        print("   1. Run database migration: alembic upgrade head")
        print("   2. Deploy to Railway: railway up")
        print("   3. Visit /hype in your app to see the feature!")


if __name__ == "__main__":
    asyncio.run(test_hype_feature())