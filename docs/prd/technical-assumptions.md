# Technical Assumptions

## Repository Structure: Monorepo
Following the detailed structure outlined in the Project Brief with separate apps for web (Next.js), API (FastAPI), and ML pipeline, while maintaining shared packages for types, database schemas, and utilities.

## Service Architecture
Microservices within a monorepo approach - separate services for API Gateway (Kong/AWS API Gateway), Data Ingestion Service, ML Inference Service, User Service, and future Notification Service. This provides scalability while maintaining development efficiency for a solo founder initially.

## Testing Requirements
Full testing pyramid including unit tests (pytest for backend, Jest for frontend), integration tests for API endpoints and data pipeline, and basic e2e testing for critical user workflows. Manual testing convenience methods needed for ML model validation and data quality verification.

## Additional Technical Assumptions and Requests
- **Frontend Stack**: React 18+ with TypeScript 5.0+, Next.js 14 for SSR/SSG, Zustand for state management, Tailwind CSS with Headless UI
- **Backend Stack**: FastAPI 0.100+ with async capabilities, scikit-learn for ML models, Celery with Redis for background tasks
- **Database Strategy**: PostgreSQL 15+ with TimescaleDB extension for time-series data, Redis for caching, Elasticsearch for prospect search
- **ML Infrastructure**: SHAP for model explainability, weekly model retraining during active seasons, feature store for consistent feature engineering
- **Data Integration**: Apache Airflow for pipeline orchestration, rate limiting compliance (1 req/sec for Fangraphs), comprehensive error handling and monitoring
- **Security Requirements**: JWT authentication, AES-256 encryption at rest, TLS 1.3 in transit, GDPR compliance endpoints
- **Infrastructure**: AWS/GCP with containerization (Docker/ECS), CloudFront CDN, comprehensive monitoring with DataDog/Sentry
- **Performance Targets**: Sub-3 second page loads, Redis caching with 30-minute TTL for rankings, database query optimization with strategic indexing
