# Manual Steps Required

ShipFlow converted **14/15 functional nodes** automatically.
**1 item** needs your attention.

---

## 1. Blotato Account IDs - Configuration Required

**Why manual:** Blotato requires your personal account IDs for each social platform. These are unique to your Blotato account.

**Time to complete:** ~10 minutes

### Steps:

1. **Log into Blotato**
   - Go to [https://blotato.com](https://blotato.com)
   - Sign in to your account

2. **Get your Account IDs**
   - Go to Settings > API
   - Or create a test post and note the account IDs shown

3. **Update the backend code**

   Open `backend/app.py` and find the `post_to_platform` function around line 180.

   Currently, the code posts to platforms but doesn't specify account IDs. You need to:

   **Option A: Add account IDs to .env file**
   ```env
   # Add these to your .env file
   BLOTATO_TIKTOK_ACCOUNT_ID=your-tiktok-account-id
   BLOTATO_INSTAGRAM_ACCOUNT_ID=your-instagram-account-id
   BLOTATO_YOUTUBE_ACCOUNT_ID=your-youtube-account-id
   # ... etc for each platform
   ```

   **Option B: Hardcode for testing (not recommended for production)**
   ```python
   # In app.py, update the post_to_platform calls with your IDs
   await post_to_platform(
       platform="tiktok",
       account_id="YOUR_TIKTOK_ACCOUNT_ID",  # Replace this
       text=script_output.caption,
       media_url=media_url
   )
   ```

4. **Platforms to configure:**

   | Platform | Where to find Account ID |
   |----------|-------------------------|
   | TikTok | Blotato > Create Post > Select TikTok > Note the account ID |
   | Instagram | Blotato > Create Post > Select Instagram > Note the account ID |
   | YouTube | Blotato > Create Post > Select YouTube > Note the account ID |
   | LinkedIn | Blotato > Create Post > Select LinkedIn > Note the account ID |
   | Twitter/X | Blotato > Create Post > Select Twitter > Note the account ID |
   | Facebook | Blotato > Create Post > Select Facebook > Note page ID too |
   | Threads | Blotato > Create Post > Select Threads > Note the account ID |
   | Bluesky | Blotato > Create Post > Select Bluesky > Note the account ID |
   | Pinterest | Blotato > Create Post > Select Pinterest > Note board ID too |

### Test it:

```bash
# Start the backend
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
uvicorn app:app --reload

# Test the config endpoint
curl http://localhost:8000/config
```

---

## 2. Schedule Trigger - Architecture Decision (Optional)

**Why manual:** The original n8n workflow runs daily at 10am. For Python, you have options.

**Time to complete:** ~15 minutes (if needed)

### Options:

**Option A: Manual trigger only (default)**
- Current setup - trigger via API or frontend
- No changes needed

**Option B: System cron job**
```bash
# Add to crontab (Linux/Mac)
crontab -e

# Run daily at 10am
0 10 * * * curl -X POST http://localhost:8000/workflow/run -H "Content-Type: application/json" -d '{"industry": "real estate"}'
```

**Option C: Celery + Redis (production)**
1. Uncomment redis in `docker-compose.yml`
2. Uncomment celery in `requirements.txt`
3. Add Celery beat scheduler:

```python
# tasks.py (create new file)
from celery import Celery
from celery.schedules import crontab

app = Celery('tasks', broker='redis://localhost:6379/0')

app.conf.beat_schedule = {
    'daily-viral-news': {
        'task': 'tasks.run_workflow',
        'schedule': crontab(hour=10, minute=0),
    },
}

@app.task
def run_workflow():
    # Import and run the workflow
    import asyncio
    from app import run_full_workflow, WorkflowInput
    asyncio.run(run_full_workflow(WorkflowInput()))
```

---

## 3. HeyGen Avatar Setup - One-Time Setup

**Why manual:** You need to create your avatar in HeyGen first.

**Time to complete:** ~10 minutes

### Steps:

1. **Sign up for HeyGen API plan**
   - Go to [https://www.heygen.com/api-pricing](https://www.heygen.com/api-pricing)
   - Choose a plan with API access

2. **Create your avatar**
   - Upload a PHOTO (talking photo) or VIDEO (video avatar)
   - Tutorial: [https://youtu.be/_jogmHuuKXk](https://youtu.be/_jogmHuuKXk)

3. **Find your correct Avatar ID using the API**

   Start the backend, then call this endpoint to see all your avatars:
   ```bash
   curl http://localhost:8000/heygen/talking-photos
   ```

   This returns:
   - `your_photos` - Your custom uploaded avatars with image preview URLs
   - `current_id` - The ID currently configured in .env

   **Look at each `image_url` in `your_photos` to visually identify your avatar, then copy its `id`.**

4. **Update .env with correct IDs**
   ```env
   HEYGEN_API_KEY=your-api-key
   HEYGEN_AVATAR_TYPE=talking_photo
   HEYGEN_TALKING_PHOTO_ID=your-talking-photo-id
   HEYGEN_VOICE_ID=your-voice-id
   ```

### Troubleshooting: Wrong Avatar Appearing?

If your videos show the wrong person:

1. Call `GET /heygen/talking-photos` to list all your avatars
2. Find your avatar by checking each `image_url`
3. Copy the correct `id`
4. Update `HEYGEN_TALKING_PHOTO_ID` in `.env`
5. Restart the backend

### Optional: Green screen background

If you have a green screen avatar (video avatars only, not talking photos):
```env
HEYGEN_HAS_BACKGROUND=true
HEYGEN_BACKGROUND_VIDEO_URL=https://your-background-video-url.mp4
```

---

## Checklist

- [ ] Blotato API key added to .env
- [ ] Blotato account IDs configured
- [ ] HeyGen API key added to .env
- [ ] HeyGen avatar ID added to .env
- [ ] HeyGen voice ID added to .env
- [ ] Perplexity API key added to .env
- [ ] OpenAI API key added to .env
- [ ] Tested with `curl http://localhost:8000/config`
- [ ] Ran full workflow test

---

## Need Help?

Ask Claude: "Help me complete [specific step] from MANUAL_STEPS.md"

**Once complete, you can delete this file.**
