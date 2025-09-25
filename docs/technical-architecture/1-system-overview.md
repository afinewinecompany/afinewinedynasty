# 1. System Overview

## High-Level Architecture

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

## Core Services

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
