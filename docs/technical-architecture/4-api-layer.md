# 4. API Layer

## Core Endpoints

**Authentication & User Management:**
```
POST /api/auth/register          # User registration
POST /api/auth/login             # JWT token generation
POST /api/auth/refresh           # Token refresh
GET  /api/users/profile          # User profile
PUT  /api/users/subscription     # Stripe subscription management
```

**Prospect Data:**
```
GET  /api/prospects              # Paginated prospect rankings
GET  /api/prospects/{id}         # Individual prospect profile
GET  /api/prospects/search       # Fuzzy search prospects
GET  /api/prospects/compare      # Compare multiple prospects
GET  /api/prospects/filters      # Available filter options
```

**ML Predictions:**
```
POST /api/ml/predict/{id}        # Individual prospect prediction
POST /api/ml/batch-predict       # Batch predictions (premium)
GET  /api/ml/explanations/{id}   # SHAP-based explanations
```

**Fantrax Integration:**
```
GET  /api/integrations/fantrax/auth    # OAuth authorization URL
POST /api/integrations/fantrax/callback # OAuth callback handler
GET  /api/integrations/fantrax/roster  # Sync user roster
GET  /api/integrations/fantrax/recommendations # Personalized recommendations
```

## Data Flow

**Typical User Session Flow:**
1. User authenticates → JWT token issued
2. Dashboard loads → Cached rankings retrieved from Redis
3. Prospect clicked → Real-time data fetched from PostgreSQL
4. ML prediction requested → Inference service called
5. SHAP explanation generated → Narrative cached in Redis

**API Response Caching Strategy:**
- **Rankings**: 30-minute TTL, refreshed on data updates
- **Prospect Profiles**: 1-hour TTL, invalidated on data changes
- **ML Predictions**: 24-hour TTL, updated with model retraining
- **Search Results**: 15-minute TTL, short cache for dynamic data

---
