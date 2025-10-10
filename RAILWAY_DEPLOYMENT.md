# Railway Deployment Guide - Automatic Social Data Collection

## Overview
Your HYPE feature includes automatic background data collection from social media platforms (Twitter/X, Reddit, Bluesky). This guide explains how it works and how to set it up on Railway.

## How Automatic Collection Works

The system uses **APScheduler** to run background tasks automatically when the API server starts. No manual intervention needed!

### Scheduled Tasks

1. **Top Players Collection** - Every 30 minutes
   - Collects social data for top 50 prospects
   - Collects for trending players (HYPE score > 70)

2. **All Players Collection** - Every 1 hour
   - Collects data for all recently active players
   - Processes in batches to respect API rate limits

3. **HYPE Score Calculation** - Every 15 minutes
   - Recalculates HYPE scores based on new social data
   - Updates sentiment and virality metrics

4. **Data Cleanup** - Every 24 hours
   - Removes social mentions older than 30 days
   - Keeps database size manageable

### Files Involved

- `apps/api/app/services/hype_scheduler.py` - Scheduler configuration
- `apps/api/app/services/social_collector.py` - Social media API integrations
- `apps/api/app/main.py` - Starts scheduler on app startup (lines 110-117)

## Railway Deployment Setup

### Step 1: Verify Environment Variables

Your `.env` file already has the credentials. Make sure these are also set in Railway:

1. Go to your Railway project
2. Click on your API service
3. Go to **Variables** tab
4. Add/verify these variables:

```bash
# Database
DATABASE_URL=<your-railway-postgres-url>

# Social Media APIs
TWITTER_BEARER_TOKEN=AAAAAAAAAAAAAAAAAAAAAHvM4gEAAAAAJqOBzHZ1aN0pEb3jxrtgkGcBeGM%3DaG3OFsSC708Co0TV9vHG8IWFmvnqbANBjqynGKbS786rZGsiDG
REDDIT_CLIENT_ID=KJdz1w8-MrVYOQpiu14Elw
REDDIT_SECRET=nXi9h3m5wutTgo-lGMQDRQHqc8-tjg
BLUESKY_HANDLE=afinewinecompany.com
BLUESKY_APP_PASSWORD=*Leojohn081324
```

### Step 2: Deploy Latest Code

The scheduler is already configured in your code. Just push to trigger Railway deployment:

```bash
git push origin DM
```

Railway will automatically:
1. Build the new code
2. Run database migrations (`alembic upgrade head`)
3. Start the API server
4. **Automatically start the scheduler** (happens in `app.main:startup_event`)

### Step 3: Populate Initial Social Data

After deployment, you have two options:

#### Option A: Run Populate Script (Recommended for Testing)
This creates sample social data to verify everything works:

```bash
# SSH into Railway container
railway run python -m scripts.populate_social_mentions
```

#### Option B: Wait for Automatic Collection
The scheduler will start collecting real data within 30 minutes of deployment. No action needed!

### Step 4: Verify It's Working

Check the Railway logs to confirm the scheduler started:

```
INFO: Starting HYPE scheduler...
INFO: HYPE scheduler started successfully
INFO: Starting top players HYPE data collection
INFO: Collected HYPE data for Max Clark
```

You can also check via API:

```bash
curl https://your-api.railway.app/api/v1/hype/player/max-clark/social-feed
```

## Monitoring & Logs

### View Scheduler Activity

In Railway logs, look for:
- `Starting top players HYPE data collection` - Every 30 min
- `Collected HYPE data for [Player Name]` - After each collection
- `Updated HYPE score for [Player Name]` - After score calculations

### Check Collection Stats

```bash
# Using Railway CLI
railway run python -c "
from app.db.database import SyncSessionLocal
from app.models.hype import SocialMention
from sqlalchemy import func

db = SyncSessionLocal()
count = db.query(func.count(SocialMention.id)).scalar()
print(f'Total social mentions collected: {count}')
db.close()
"
```

## Manual Trigger (For Testing)

If you want to trigger data collection manually without waiting:

```bash
curl -X POST https://your-api.railway.app/api/v1/hype/admin/collect-social-data?limit=10
```

This will immediately collect data for the top 10 players.

## Troubleshooting

### Scheduler Not Running

**Symptom:** Logs don't show "HYPE scheduler started"

**Solution:**
1. Check Railway logs for errors during startup
2. Verify `start_hype_scheduler()` is called in `app/main.py`
3. Ensure `apscheduler` is installed (it's in `requirements.txt`)

### No Data Being Collected

**Symptom:** Scheduler runs but no mentions in database

**Possible causes:**

1. **Missing API credentials**
   - Check Railway environment variables are set correctly
   - Verify credentials are valid (test locally first)

2. **Rate limits hit**
   - Twitter: 300 calls per 15 min
   - Reddit: 60 calls per minute
   - Bluesky: 100 calls per 5 min
   - Check logs for rate limit errors

3. **No matching players**
   - Ensure PlayerHype table has player records
   - Run: `railway run python -m scripts.populate_hype_data`

### API Credentials Invalid

**Symptom:** Logs show "Authentication failed" or "401 Unauthorized"

**For Twitter:**
- Verify Bearer Token is valid
- Check it has v2 API access
- May need to regenerate token in Twitter Developer Portal

**For Reddit:**
- Verify Client ID and Secret are correct
- Check app is set to "script" type in Reddit apps

**For Bluesky:**
- Verify handle format: `username.bsky.social`
- App password must be generated from Bluesky settings (not your main password)

## Production Considerations

### Database Size Management

Social mentions can grow quickly. The scheduler automatically deletes mentions older than 30 days.

To adjust retention period, edit `apps/api/app/services/hype_scheduler.py`:

```python
# Line 218
cutoff_date = datetime.utcnow() - timedelta(days=30)  # Change 30 to your preference
```

### Rate Limiting

The collector respects API rate limits automatically. If you have many players:

1. Reduce collection frequency in `hype_scheduler.py`:
   ```python
   IntervalTrigger(minutes=60)  # Instead of 30
   ```

2. Reduce batch size:
   ```python
   for player in players_to_update[:10]:  # Instead of 20
   ```

### Performance

The scheduler runs in background threads and won't block API requests. However, for very large datasets (1000+ players), consider:

1. Using a separate worker dyno/service
2. Implementing Redis for better rate limit tracking
3. Moving to a job queue (Celery, RQ)

## Current Status

✅ **Scheduler configured** - Starts automatically on Railway deployment
✅ **API credentials configured** - In .env and Railway variables
✅ **Social collectors implemented** - Twitter/X, Reddit, Bluesky
✅ **Database populated** - 621 sample mentions for 100 players (local)
⏳ **Production deployment** - Will auto-collect after next Railway deploy

## Next Deploy Checklist

When you push to Railway:

- [ ] Verify all environment variables are set in Railway dashboard
- [ ] Check Railway deployment logs for "HYPE scheduler started successfully"
- [ ] Wait 30 minutes and check logs for "Collected HYPE data for..."
- [ ] Test API endpoint: `/api/v1/hype/player/{player_id}/social-feed`
- [ ] View social mentions in the web app under HYPE details

## API Endpoints for Social Data

```
GET  /api/v1/hype/leaderboard                    # HYPE leaderboard
GET  /api/v1/hype/player/{player_id}             # Player HYPE details
GET  /api/v1/hype/player/{player_id}/social-feed # Social mentions
POST /api/v1/hype/admin/collect-social-data      # Manual trigger
```

All endpoints are **public** (no authentication required).

---

**Need help?** Check Railway logs or the social_collector.py source code for detailed error messages.
