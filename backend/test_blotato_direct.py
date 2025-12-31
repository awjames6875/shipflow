"""
Direct Blotato test - bypasses server entirely.
Run with: python test_blotato_direct.py
"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

BLOTATO_API_KEY = os.getenv("BLOTATO_API_KEY")
ACCOUNTS = {
    "tiktok": os.getenv("BLOTATO_TIKTOK_ACCOUNT_ID"),
    "instagram": os.getenv("BLOTATO_INSTAGRAM_ACCOUNT_ID"),
    "youtube": os.getenv("BLOTATO_YOUTUBE_ACCOUNT_ID"),
    "facebook": os.getenv("BLOTATO_FACEBOOK_ACCOUNT_ID"),
    "twitter": os.getenv("BLOTATO_TWITTER_ACCOUNT_ID"),
    "bluesky": os.getenv("BLOTATO_BLUESKY_ACCOUNT_ID"),
}
FACEBOOK_PAGE_ID = os.getenv("BLOTATO_FACEBOOK_PAGE_ID")

TEST_VIDEO = "https://database.blotato.io/storage/v1/object/public/public_media/4ddd33eb-e811-4ab5-93e1-2cd0b7e8fb3f/videogen-4c61a730-7eb2-47e9-a3a3-524740a1b877.mp4"
TEST_CAPTION = "Testing Blotato from Python! #test"
TEST_TITLE = "Test Video"


async def upload_media(client: httpx.AsyncClient, video_url: str) -> str:
    """Upload media to Blotato"""
    response = await client.post(
        "https://backend.blotato.com/v2/media",
        headers={"blotato-api-key": BLOTATO_API_KEY, "Content-Type": "application/json"},
        json={"url": video_url}
    )
    response.raise_for_status()
    return response.json()["url"]


async def post_to_platform(client: httpx.AsyncClient, platform: str, account_id: str, media_url: str) -> dict:
    """Post to a single platform"""
    # Build target based on platform
    target = {"targetType": platform}

    if platform == "facebook":
        target["pageId"] = FACEBOOK_PAGE_ID
    elif platform == "youtube":
        target["title"] = TEST_TITLE
        target["containsSyntheticMedia"] = True
        target["privacyStatus"] = "public"
        target["shouldNotifySubscribers"] = True
    elif platform == "tiktok":
        target["isAiGenerated"] = True
        target["privacyLevel"] = "PUBLIC_TO_EVERYONE"
        target["disabledComments"] = False
        target["disabledDuet"] = False
        target["disabledStitch"] = False
        target["isBrandedContent"] = False
        target["isYourBrand"] = False

    payload = {
        "post": {
            "accountId": account_id,  # NO acc_ prefix!
            "content": {
                "text": TEST_CAPTION,
                "mediaUrls": [media_url],
                "platform": platform
            },
            "target": target
        }
    }

    response = await client.post(
        "https://backend.blotato.com/v2/posts",
        headers={"blotato-api-key": BLOTATO_API_KEY, "Content-Type": "application/json"},
        json=payload
    )

    if response.status_code >= 400:
        return {"error": response.text, "status_code": response.status_code}
    return response.json()


async def main():
    print("=" * 60)
    print("BLOTATO DIRECT TEST")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Step 1: Upload
        print("\n[1] Uploading media...")
        try:
            media_url = await upload_media(client, TEST_VIDEO)
            print(f"    SUCCESS: {media_url}")
        except Exception as e:
            print(f"    FAILED: {e}")
            return

        # Step 2: Post to each platform
        print("\n[2] Posting to platforms...")
        results = {}

        for platform, account_id in ACCOUNTS.items():
            if not account_id:
                print(f"    {platform}: SKIPPED (no account ID)")
                continue

            print(f"    {platform} (account {account_id})...", end=" ")
            try:
                result = await post_to_platform(client, platform, account_id, media_url)
                if "error" in result:
                    print(f"FAILED - {result}")
                    results[platform] = "FAILED"
                else:
                    print(f"SUCCESS - {result.get('postSubmissionId', 'OK')}")
                    results[platform] = "SUCCESS"
            except Exception as e:
                print(f"FAILED - {e}")
                results[platform] = "FAILED"

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        success = sum(1 for v in results.values() if v == "SUCCESS")
        failed = sum(1 for v in results.values() if v == "FAILED")
        print(f"Success: {success}")
        print(f"Failed: {failed}")
        print(f"\nCheck dashboard: https://my.blotato.com/api-dashboard")


if __name__ == "__main__":
    asyncio.run(main())
