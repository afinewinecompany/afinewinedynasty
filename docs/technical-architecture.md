# A Fine Wine Dynasty - Technical Architecture

*Generated: 2025-09-24*

---

## 1. System Overview

### High-Level Architecture

A Fine Wine Dynasty is built as a **microservices architecture within a monorepo**, optimized for a 6-month solo development timeline while maintaining scalability for 1000+ users. The system follows a three-tier architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend Layer                           │
├─────────────────────────────────────────────────────────────────┤
│ Next.js 14 (React 18 + TypeScript)                            │
│ • Prospect Rankings Dashboard                                  │
│ • Individual Prospect Profiles                               │
│ • User Authentication & Subscription Management              │
│ • Fantrax Integration Interface                              │
└─────────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway Layer                         │
├─────────────────────────────────────────────────────────────────┤
│ Kong/AWS API Gateway                                           │
│ • Rate Limiting (100/min free, 1000/min premium)             │
│ • JWT Authentication                                          │
│ • Request Routing                                             │
│ • API Caching                                                 │
└─────────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────────┐
│                     Microservices Layer                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   User Service  │  │   Data Service  │  │  ML Service     │ │
│  │                 │  │                 │  │                 │ │
│  │ • Authentication│  │ • Data Ingestion│  │ • Model Training│ │
│  │ • Subscriptions │  │ • Data Pipeline │  │ • Predictions   │ │
│  │ • Fantrax Sync  │  │ • Data Quality  │  │ • Explanations  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────────┐
│                      Data Storage Layer                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   PostgreSQL    │  │      Redis      │  │  Elasticsearch  │ │
│  │   + TimescaleDB │  │                 │  │                 │ │
│  │                 │  │ • Session Cache │  │ • Prospect      │ │
│  │ • Prospect Data │  │ • Rankings Cache│  │   Search        │ │
│  │ • User Data     │  │ • Task Queue    │  │ • Fuzzy Match   │ │
│  │ • ML Features   │  │ • Rate Limiting │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Core Services

**User Service (FastAPI)**
- JWT-based authentication with 15-min access tokens
- Stripe subscription management
- Fantrax OAuth integration
- User preferences and settings

**Data Service (FastAPI)**
- Multi-source data ingestion (MLB API, Fangraphs)
- Data validation and cleaning
- Real-time prospect updates
- Historical data processing

**ML Service (FastAPI)**
- Model training pipeline (XGBoost/LightGBM)
- Real-time inference (<500ms)
- SHAP-based explanations
- Confidence scoring (High/Medium/Low)

**Frontend Service (Next.js)**
- Server-side rendering for SEO
- Progressive Web App capabilities
- Mobile-first responsive design
- Real-time data updates

---

## 2. Data Pipeline

### Historical Data Ingestion

The system processes 15+ years of historical minor league data (~50,000 prospect records) for ML model training:

```
External Sources → Raw Data Ingestion → Data Validation → Feature Engineering → ML Training Data
     ↓                    ↓                    ↓               ↓                    ↓
• MLB Stats API      • Apache Airflow     • Data Quality    • Age Adjustments   • PostgreSQL
• Fangraphs         • Error Handling      • Duplicate       • Rate Statistics    • TimescaleDB
• Baseball America  • Rate Limiting       • Detection       • Level Progression  • Feature Store
```

**Data Sources & Integration:**
- **MLB Stats API**: Free tier, official player data, 1000 requests/day limit
- **Fangraphs**: Web scraping with 1 req/sec rate limiting, scouting grades
- **Baseball America**: Potential partnership for additional scouting data

**Data Processing Pipeline:**
```python
# Apache Airflow DAG structure
prospect_data_pipeline = DAG(
    'prospect_data_ingestion',
    schedule_interval='@daily',
    start_date=datetime(2025, 1, 1)
)

# Task sequence
extract_mlb_data >> extract_fangraphs_data >> validate_data >>
clean_data >> feature_engineering >> update_rankings >> cache_results
```

### Real-Time Processing

**Daily Update Process:**
1. **6:00 AM ET**: Automated data collection from all sources
2. **6:30 AM ET**: Data validation and deduplication
3. **7:00 AM ET**: ML model inference for updated prospects
4. **7:30 AM ET**: Cache refresh and rankings update
5. **8:00 AM ET**: User notifications for significant changes

**Data Quality Assurance:**
- Schema validation using Pydantic models
- Statistical outlier detection for performance metrics
- Cross-source data consistency checks
- Data freshness monitoring with alerts

---

## 3. ML Infrastructure

### Training Pipeline

**Model Architecture:**
- **Primary Model**: XGBoost Classifier for binary classification
- **Target Variable**: MLB success (>500 PA or >100 IP within 4 years)
- **Features**: 50+ engineered features including:
  - Age-adjusted performance metrics
  - Level progression rates
  - Scouting grades (20-80 scale normalized)
  - Historical comparisons

**Training Infrastructure:**
```python
# Model training configuration
training_config = {
    'model_type': 'xgboost.XGBClassifier',
    'hyperparameters': {
        'n_estimators': 1000,
        'max_depth': 6,
        'learning_rate': 0.01,
        'subsample': 0.8,
        'colsample_bytree': 0.8
    },
    'validation_strategy': 'time_series_split',
    'retraining_schedule': 'weekly_during_season',
    'target_accuracy': 0.65
}
```

**Model Versioning & Deployment:**
- MLflow for experiment tracking and model registry
- A/B testing framework for model comparison
- Automated rollback on performance degradation
- Model artifacts stored in S3/GCS with versioning

### Inference Service

**Real-Time Prediction API:**
```python
@app.post("/api/ml/predict")
@limiter.limit("10/minute")
async def predict_prospect_success(
    prospect_id: int,
    user: User = Depends(get_current_user)
):
    # Load cached model
    model = await get_cached_model()

    # Get prospect features
    features = await get_prospect_features(prospect_id)

    # Generate prediction with SHAP explanation
    prediction = model.predict_proba([features])[0][1]
    shap_values = await generate_shap_explanation(model, features)

    # Determine confidence level
    confidence = determine_confidence_level(prediction, shap_values)

    return PredictionResponse(
        prospect_id=prospect_id,
        success_probability=prediction,
        confidence_level=confidence,
        explanation=generate_narrative(shap_values)
    )
```

**Performance Optimizations:**
- Model caching in Redis with 1-hour TTL
- Batch prediction capability for rankings updates
- Connection pooling for database queries
- Async processing for non-blocking inference

---

## 4. API Layer

### Core Endpoints

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

### Data Flow

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

## 5. Database Design

### Core Schema

**Prospects Table:**
```sql
CREATE TABLE prospects (
    id SERIAL PRIMARY KEY,
    mlb_id VARCHAR(10) UNIQUE,
    name VARCHAR(100) NOT NULL,
    position VARCHAR(10) NOT NULL,
    organization VARCHAR(50),
    level VARCHAR(20),
    age INTEGER,
    eta_year INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_prospects_organization ON prospects(organization);
CREATE INDEX idx_prospects_position ON prospects(position);
CREATE INDEX idx_prospects_eta ON prospects(eta_year);
```

**Time-Series Performance Data (TimescaleDB):**
```sql
-- Hypertable for time-series data
CREATE TABLE prospect_stats (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),
    season INTEGER NOT NULL,
    level VARCHAR(20) NOT NULL,
    date_recorded DATE NOT NULL,

    -- Hitting statistics
    games_played INTEGER,
    at_bats INTEGER,
    hits INTEGER,
    home_runs INTEGER,
    rbi INTEGER,
    stolen_bases INTEGER,
    walks INTEGER,
    strikeouts INTEGER,
    batting_avg DECIMAL(4,3),
    on_base_pct DECIMAL(4,3),
    slugging_pct DECIMAL(4,3),

    -- Pitching statistics
    innings_pitched DECIMAL(5,1),
    earned_runs INTEGER,
    era DECIMAL(4,2),
    whip DECIMAL(4,3),
    strikeouts_per_nine DECIMAL(4,2),
    walks_per_nine DECIMAL(4,2),

    -- Performance metrics
    woba DECIMAL(4,3),
    wrc_plus INTEGER,

    recorded_at TIMESTAMP DEFAULT NOW()
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('prospect_stats', 'date_recorded');
```

**ML Features & Predictions:**
```sql
CREATE TABLE ml_predictions (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),
    model_version VARCHAR(20) NOT NULL,
    success_probability DECIMAL(4,3),
    confidence_level VARCHAR(10) CHECK (confidence_level IN ('High', 'Medium', 'Low')),
    feature_importance JSONB, -- SHAP values
    narrative TEXT, -- Generated explanation
    generated_at TIMESTAMP DEFAULT NOW()
);

-- Composite index for latest predictions
CREATE INDEX idx_predictions_latest ON ml_predictions(prospect_id, generated_at DESC);
```

**User Management:**
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    subscription_tier VARCHAR(20) DEFAULT 'free'
        CHECK (subscription_tier IN ('free', 'premium')),
    stripe_customer_id VARCHAR(50),
    fantrax_user_id VARCHAR(50),
    fantrax_refresh_token TEXT,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER REFERENCES users(id),
    access_token_hash VARCHAR(255),
    refresh_token_hash VARCHAR(255),
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Data Relationships

```
prospects (1) ←→ (∞) prospect_stats [Time-series performance data]
prospects (1) ←→ (∞) scouting_grades [Multi-source scouting data]
prospects (1) ←→ (∞) ml_predictions [ML model outputs]
users (1) ←→ (∞) user_watchlists [Prospect tracking]
users (1) ←→ (∞) fantrax_rosters [League integration]
```

### Database Performance Strategy

**Partitioning Strategy:**
- **prospect_stats**: Partitioned by date_recorded (monthly partitions)
- **ml_predictions**: Partitioned by generated_at (monthly partitions)
- **user_sessions**: Automatic cleanup of expired sessions

**Indexing Strategy:**
```sql
-- Critical performance indexes
CREATE INDEX idx_stats_prospect_season ON prospect_stats(prospect_id, season);
CREATE INDEX idx_stats_date_recorded ON prospect_stats(date_recorded);
CREATE INDEX idx_scouting_source_updated ON scouting_grades(source, updated_at);
CREATE INDEX idx_users_subscription ON users(subscription_tier);
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at);
```

---

## 6. Deployment Strategy

### Infrastructure Overview

**Containerized Deployment (AWS/GCP):**
```yaml
# Docker Compose structure for local development
version: '3.8'
services:
  web:
    build: ./apps/web
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_API_URL=http://api:8000

  api:
    build: ./apps/api
    ports: ["8000:8000"]
    depends_on: [postgres, redis]
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/afwd
      - REDIS_URL=redis://redis:6379

  ml-service:
    build: ./apps/ml-pipeline
    depends_on: [postgres, redis]

  postgres:
    image: timescale/timescaledb:2.11.0-pg15
    environment:
      - POSTGRES_DB=afwd
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
```

### Production Architecture

**AWS Infrastructure:**
- **Compute**: ECS Fargate for auto-scaling microservices
- **Database**: RDS PostgreSQL with TimescaleDB extension
- **Caching**: ElastiCache Redis cluster
- **Storage**: S3 for model artifacts and backups
- **CDN**: CloudFront for static assets and API caching
- **Load Balancer**: ALB with SSL termination

**Kubernetes Alternative (GCP):**
```yaml
# Kubernetes deployment example
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-service
  template:
    metadata:
      labels:
        app: api-service
    spec:
      containers:
      - name: api
        image: gcr.io/project/api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
```

### Scaling Strategy

**Horizontal Scaling Approach:**
- **Frontend**: CDN + multiple Edge locations
- **API Services**: Auto-scaling based on CPU/memory usage
- **ML Service**: Queue-based processing with worker pools
- **Database**: Read replicas for query distribution

**Performance Targets:**
- **Page Load Time**: <3 seconds (95th percentile)
- **API Response Time**: <500ms for ML predictions
- **Database Queries**: <100ms for most operations
- **Uptime**: 99.9% availability during peak periods

### Monitoring & Observability

**Application Monitoring:**
```python
# Example monitoring setup
from prometheus_client import Counter, Histogram, generate_latest

# Metrics collection
REQUEST_COUNT = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('api_request_duration_seconds', 'Request latency')
ML_PREDICTION_ACCURACY = Histogram('ml_prediction_accuracy', 'Model prediction accuracy')

@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path).inc()
    REQUEST_LATENCY.observe(process_time)

    return response
```

**Key Monitoring Metrics:**
- **Application**: Request latency, error rates, throughput
- **ML Models**: Prediction accuracy, inference time, feature drift
- **Database**: Query performance, connection pool usage, cache hit rates
- **Infrastructure**: CPU, memory, disk usage, network latency

**Alerting Strategy:**
- **Critical**: API down, database connection failures, model accuracy drops below 60%
- **Warning**: High latency (>1s), cache misses >50%, disk usage >80%
- **Info**: Successful deployments, daily data ingestion completion

### CI/CD Pipeline

**GitHub Actions Workflow:**
```yaml
name: Deploy to Production
on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Tests
        run: |
          # Python backend tests
          cd apps/api && python -m pytest tests/
          # Frontend tests
          cd apps/web && npm run test
          # ML pipeline tests
          cd apps/ml-pipeline && python -m pytest tests/

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to ECS
        run: |
          # Build and push Docker images
          # Update ECS service definitions
          # Run database migrations
          # Warm caches
```

**Deployment Stages:**
1. **Development**: Feature branch → PR → automated testing
2. **Staging**: Merge to develop → staging deployment → integration tests
3. **Production**: Merge to main → blue/green deployment → health checks

---

## Technical Constraints & Considerations

### Performance Requirements

**Response Time Targets:**
- Prospect rankings page: <2 seconds initial load
- ML predictions: <500ms per request
- Search results: <1 second with fuzzy matching
- Database queries: <100ms for 95% of operations

**Scalability Targets:**
- Support 1000+ concurrent users
- Handle 150+ daily active users with 40% weekend spikes
- Process 100K+ API requests daily
- Maintain performance during data ingestion periods

### Security Implementation

**Authentication & Authorization:**
```python
# JWT token implementation
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
import jwt

security = HTTPBearer()

async def get_current_user(token: str = Depends(security)):
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return await get_user(user_id)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
```

**Data Protection:**
- **Encryption at Rest**: AES-256 for sensitive user data
- **Encryption in Transit**: TLS 1.3 for all communications
- **API Security**: Rate limiting, CORS configuration, input validation
- **GDPR Compliance**: User data export/deletion endpoints

### Development Timeline Constraints

**6-Month MVP Development Schedule:**
- **Months 1-2**: Foundation (database, auth, basic API)
- **Months 3-4**: ML pipeline and data integration
- **Months 5-6**: Frontend, Fantrax integration, testing

**Critical Path Dependencies:**
1. Historical data acquisition and processing
2. ML model training and validation
3. Fantrax API integration approval
4. Performance optimization and testing

This technical architecture provides a solid foundation for A Fine Wine Dynasty, balancing development speed with scalability requirements while meeting all specified performance and functional requirements within the 6-month timeline.