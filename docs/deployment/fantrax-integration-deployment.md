# Fantrax Integration Deployment Guide

**Story:** 4.3 - Fantrax League Integration
**Quality Gate:** PASS (95/100)
**Date:** 2025-10-03

## Overview

This guide covers deployment requirements for the Fantrax integration feature, including environment configuration, database migration, monitoring setup, and rollout recommendations.

---

## Pre-Deployment Checklist

### 1. Database Migration

**Status:** ✅ Migration script ready at `apps/api/alembic/versions/009_add_fantrax_tables.py`

**Action Required:**
```bash
cd apps/api
python -m alembic upgrade head
```

**What it does:**
- Adds `fantrax_connected_at` column to `users` table
- Creates `fantrax_leagues` table for league data storage
- Creates `fantrax_rosters` table for roster data
- Creates `fantrax_sync_history` table for sync tracking
- Adds GIN index on `fantrax_rosters.positions` for performance
- Adds composite indexes for `user_id + league_id` queries

**Rollback:**
```bash
cd apps/api
python -m alembic downgrade -1
```

---

### 2. Environment Variables

**Location:** `apps/api/.env`

**Required Variables:**
```bash
# Fantrax OAuth Configuration
FANTRAX_CLIENT_ID=<your_client_id>
FANTRAX_CLIENT_SECRET=<your_client_secret>
FANTRAX_REDIRECT_URI=https://yourdomain.com/integrations/fantrax/callback

# For local development:
# FANTRAX_REDIRECT_URI=http://localhost:3000/integrations/fantrax/callback
```

**How to obtain credentials:**
1. Register your application at https://www.fantrax.com/developer
2. Configure OAuth callback URL to match your `FANTRAX_REDIRECT_URI`
3. Copy Client ID and Client Secret to your `.env` file

**Security Note:**
- Never commit actual credentials to version control
- Use environment-specific configuration management (e.g., AWS Secrets Manager, HashiCorp Vault)
- Rotate secrets regularly (quarterly recommended)

---

### 3. Redis Configuration

**Required:** Redis must be running for caching layer

**Verify Redis is running:**
```bash
# Linux/Mac
redis-cli ping
# Expected output: PONG

# Windows (if using Redis service)
# Check Services panel for "Redis" service status
```

**Cache TTL Configuration:**
- **League Data:** 24 hours (league settings rarely change)
- **Roster Data:** 1 hour (rosters change during games)
- **Recommendations:** 30 minutes (balance freshness with performance)
- **Analysis Results:** 1 hour (team needs evolve slowly)

**Redis Memory Recommendations:**
- Allocate at least 512MB for Fantrax cache
- Monitor memory usage with `redis-cli INFO memory`
- Configure `maxmemory-policy allkeys-lru` for automatic eviction

---

### 4. Dependencies

**Backend (Python):**
All dependencies already included in `apps/api/requirements.txt`:
- `httpx` - Async HTTP client for Fantrax API calls
- `cryptography` - Fernet encryption for token storage
- `redis` - Redis caching client

**Frontend (TypeScript):**
All dependencies already included in `apps/web/package.json`:
- React 18
- Next.js 14
- TypeScript 5+

**No additional installation required** - dependencies are part of existing setup.

---

## Deployment Recommendations

### Feature Flag Strategy

**Recommendation:** Use gradual rollout to premium users

**Implementation Options:**

#### Option 1: Manual Feature Flag
```python
# In apps/api/app/core/config.py
FANTRAX_FEATURE_ENABLED = os.getenv("FANTRAX_FEATURE_ENABLED", "false").lower() == "true"

# In endpoint decorators
@require_feature_flag("fantrax")
```

#### Option 2: User-Based Rollout
```python
# Rollout to 10% of premium users initially
def is_fantrax_enabled_for_user(user_id: int) -> bool:
    if settings.FANTRAX_ROLLOUT_PERCENTAGE == 100:
        return True
    return (user_id % 100) < settings.FANTRAX_ROLLOUT_PERCENTAGE
```

**Recommended Rollout Schedule:**

| Phase | Duration | Target Users | Monitoring Focus |
|-------|----------|--------------|------------------|
| Phase 1 | Week 1 | 10% premium users | Error rates, OAuth success rate |
| Phase 2 | Week 2 | 25% premium users | Sync performance, cache hit rates |
| Phase 3 | Week 3 | 50% premium users | Database load, API latency |
| Phase 4 | Week 4+ | 100% premium users | Overall stability |

---

## Monitoring Requirements

### Key Metrics to Track

#### 1. **OAuth Flow Metrics**
```
Metric: fantrax_oauth_success_rate
Target: > 95%
Alert Threshold: < 90%

Metric: fantrax_oauth_duration_ms
Target: < 3000ms
Alert Threshold: > 5000ms
```

#### 2. **Roster Sync Metrics**
```
Metric: sync_duration_ms
Target: < 5000ms for 40-player roster
Alert Threshold: > 10000ms
Tracked in: fantrax_sync_history.sync_duration_ms

Metric: sync_success_rate
Target: > 98%
Alert Threshold: < 95%
```

#### 3. **Cache Performance Metrics**
```
Metric: fantrax_cache_hit_rate
Target: > 75%
Alert Threshold: < 50%

Metric: redis_memory_usage_mb
Target: < 400MB
Alert Threshold: > 450MB (of 512MB allocated)
```

#### 4. **API Performance Metrics**
```
Metric: recommendation_generation_duration_ms
Target: < 2000ms
Alert Threshold: > 4000ms

Metric: fantrax_api_rate_limit_errors
Target: 0
Alert Threshold: > 5 per hour
```

#### 5. **Database Performance Metrics**
```
Metric: fantrax_roster_query_duration_ms
Target: < 100ms (with GIN index)
Alert Threshold: > 500ms

Metric: database_connection_pool_usage
Target: < 70%
Alert Threshold: > 85%
```

### Monitoring Implementation

**Option 1: Application-Level Logging**
```python
# Log sync metrics
logger.info(
    "fantrax_sync_completed",
    extra={
        "league_id": league_id,
        "sync_duration_ms": sync_duration,
        "players_synced": players_count,
        "cache_hit": cache_hit
    }
)
```

**Option 2: Metrics Collection (Recommended)**
```python
# Using Prometheus/StatsD
from prometheus_client import Counter, Histogram

sync_duration_histogram = Histogram(
    'fantrax_sync_duration_seconds',
    'Time taken to sync Fantrax roster',
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0]
)

cache_hit_counter = Counter(
    'fantrax_cache_hits_total',
    'Number of cache hits for Fantrax data'
)
```

---

## Performance Validation

### Load Testing Recommendations

**Target:** Support 100+ concurrent Fantrax syncs

**Test Scenarios:**

1. **OAuth Flow Load Test**
   - Simulate 50 concurrent OAuth callbacks
   - Verify < 3s response time
   - Validate CSRF protection under load

2. **Roster Sync Load Test**
   - Simulate 100 concurrent roster syncs (40 players each)
   - Target: < 5s per sync
   - Monitor database connection pool

3. **Recommendation Generation Load Test**
   - 50 concurrent recommendation requests
   - Target: < 2s response time
   - Validate cache effectiveness

**Load Testing Tools:**
- k6 (recommended): https://k6.io/
- Locust: https://locust.io/
- Apache JMeter

---

## Security Checklist

- ✅ Refresh tokens encrypted at rest using Fernet (AES-128)
- ✅ OAuth state parameter validates CSRF attacks
- ✅ Premium tier authorization on all Fantrax endpoints
- ✅ Foreign key relationships prevent unauthorized data access
- ✅ `decrypt_value()` properly raises exceptions instead of silently failing
- ✅ JWT token validation on all protected endpoints
- ✅ Rate limiting implemented for Fantrax API calls

**Additional Security Recommendations:**

1. **Audit Logging:** Enable audit logging for all Fantrax connection/disconnection events
2. **Token Rotation:** Implement refresh token rotation policy (30-day expiration recommended)
3. **API Rate Limiting:** Monitor Fantrax API rate limits to avoid service disruption
4. **Input Validation:** All Pydantic schemas include strict validation

---

## Post-Deployment Validation

### Smoke Tests

1. **OAuth Flow Test**
   ```bash
   # Test authorization URL generation
   curl -H "Authorization: Bearer <token>" \
     https://yourapi.com/api/integrations/fantrax/auth
   ```

2. **Roster Sync Test**
   ```bash
   # Test roster sync
   curl -X POST -H "Authorization: Bearer <token>" \
     https://yourapi.com/api/integrations/fantrax/roster/sync \
     -d '{"league_id": "test_league_123"}'
   ```

3. **Recommendations Test**
   ```bash
   # Test personalized recommendations
   curl -H "Authorization: Bearer <token>" \
     https://yourapi.com/api/integrations/fantrax/recommendations/test_league_123
   ```

### Health Checks

1. **Database Migration Verification**
   ```sql
   -- Verify tables exist
   SELECT table_name FROM information_schema.tables
   WHERE table_name LIKE 'fantrax%';

   -- Verify GIN index exists
   SELECT indexname FROM pg_indexes
   WHERE indexname = 'ix_fantrax_rosters_positions_gin';
   ```

2. **Cache Connectivity**
   ```bash
   redis-cli
   > KEYS fantrax:*
   > TTL fantrax:league:123
   ```

3. **API Endpoint Availability**
   ```bash
   # Check all endpoints return proper error (not 500)
   curl -X GET https://yourapi.com/api/integrations/fantrax/leagues
   # Expected: 401 Unauthorized (not authenticated)
   ```

---

## Rollback Plan

### If Issues Arise During Deployment

**Step 1: Disable Feature**
```bash
# Set environment variable
FANTRAX_FEATURE_ENABLED=false

# Restart API service
systemctl restart afinewinedynasty-api  # Linux
# or
pm2 restart api  # PM2
```

**Step 2: Rollback Database (if necessary)**
```bash
cd apps/api
python -m alembic downgrade -1
```

**Step 3: Clear Redis Cache**
```bash
redis-cli
> KEYS fantrax:*
> DEL <keys>  # or FLUSHDB if isolated Redis instance
```

**Step 4: Monitor Logs**
```bash
# Check for any lingering errors
tail -f /var/log/afinewinedynasty/api.log | grep fantrax
```

---

## Support & Troubleshooting

### Common Issues

**Issue 1: OAuth callback fails with "Invalid state token"**
- **Cause:** CSRF token mismatch or expired state
- **Solution:** Ensure cookies are enabled, check state token expiration (15-min recommended)

**Issue 2: Roster sync timeout**
- **Cause:** Fantrax API slow response or network issues
- **Solution:** Implement retry logic with exponential backoff (already included)

**Issue 3: High memory usage in Redis**
- **Cause:** Too many cached rosters
- **Solution:** Reduce TTL or implement LRU eviction policy

**Issue 4: GIN index not being used**
- **Cause:** Query optimizer choosing sequential scan
- **Solution:** Run `ANALYZE fantrax_rosters;` to update statistics

### Debug Mode

Enable debug logging for troubleshooting:
```bash
LOG_LEVEL=DEBUG
```

View detailed Fantrax service logs:
```python
# In apps/api/app/services/fantrax_*.py
logger.setLevel(logging.DEBUG)
```

---

## Contacts

**Feature Owner:** James (Full Stack Developer)
**QA Lead:** Quinn (Test Architect)
**Quality Gate:** docs/qa/gates/4.3-fantrax-league-integration.yml
**Traceability Matrix:** docs/qa/assessments/4.3-trace-20251003.md

---

## Change Log

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-10-03 | 1.0 | Initial deployment guide created | James (Dev) |

---

**Production Readiness:** ✅ APPROVED (95/100 quality score)
**Confidence Level:** HIGH - All acceptance criteria met, comprehensive test coverage, all critical fixes applied
