# Comprehensive Developer Setup Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Local Development](#local-development)
4. [Database Management](#database-management)
5. [API Development](#api-development)
6. [Frontend Development](#frontend-development)
7. [Testing Strategy](#testing-strategy)
8. [Debugging Guide](#debugging-guide)
9. [Common Development Tasks](#common-development-tasks)
10. [IDE Setup](#ide-setup)

## Prerequisites

### Required Software

| Software | Version | Purpose | Installation |
|----------|---------|---------|--------------|
| Node.js | 18+ | Frontend development | [nodejs.org](https://nodejs.org/) |
| Python | 3.11-3.13 | Backend development | [python.org](https://python.org/) |
| Docker | 20+ | Containerization | [docker.com](https://docker.com/) |
| PostgreSQL | 15+ | Database (optional local) | [postgresql.org](https://postgresql.org/) |
| Redis | 7+ | Caching (optional local) | [redis.io](https://redis.io/) |
| Git | 2.30+ | Version control | [git-scm.com](https://git-scm.com/) |

### System Requirements
- **RAM**: Minimum 8GB (16GB recommended)
- **Storage**: 10GB free space
- **OS**: Windows 10+, macOS 11+, Ubuntu 20.04+

## Environment Setup

### 1. Clone Repository
```bash
git clone https://github.com/your-org/afinewinedynasty.git
cd afinewinedynasty
```

### 2. Environment Files Setup

Create local environment files:
```bash
# Root environment
cp .env.example .env

# Frontend environment
cp apps/web/.env.example apps/web/.env.local

# Backend environment
cp apps/api/.env.example apps/api/.env
```

### 3. Configure Environment Variables

#### Backend (.env and apps/api/.env)
```env
# Database
POSTGRES_SERVER=localhost
POSTGRES_USER=afwd_user
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_DB=afinewinedynasty
DATABASE_URL=postgresql://afwd_user:your_secure_password_here@localhost/afinewinedynasty

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Security
SECRET_KEY=your-secret-key-generate-with-openssl-rand-hex-32
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# External Services
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
MLB_API_KEY=your_mlb_api_key
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Email (SendGrid example)
SENDGRID_API_KEY=SG.xxx
EMAIL_FROM=noreply@afinewinedynasty.com
EMAIL_FROM_NAME=A Fine Wine Dynasty

# Feature Flags
ENABLE_ML_PREDICTIONS=true
ENABLE_FANTRAX_INTEGRATION=false
```

#### Frontend (apps/web/.env.local)
```env
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_VERSION=v1

# Authentication
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your_google_client_id

# Stripe
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...

# Analytics (optional)
NEXT_PUBLIC_GA_MEASUREMENT_ID=G-XXXXXXXXXX
NEXT_PUBLIC_PLAUSIBLE_DOMAIN=afinewinedynasty.com

# Feature Flags
NEXT_PUBLIC_ENABLE_PWA=true
NEXT_PUBLIC_ENABLE_OFFLINE_MODE=true
```

## Local Development

### Option 1: Docker Development (Recommended)

```bash
# Start all services
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Start specific services
docker-compose up postgres redis  # Just databases
docker-compose up api             # Just backend
docker-compose up web             # Just frontend

# Rebuild after dependency changes
docker-compose up --build

# View logs
docker-compose logs -f api
docker-compose logs -f web
```

### Option 2: Native Development

#### Backend Setup
```bash
cd apps/api

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend Setup
```bash
cd apps/web

# Install dependencies
npm install
# or
yarn install

# Start development server
npm run dev
# or
yarn dev
```

## Database Management

### Setting Up PostgreSQL with TimescaleDB

#### Docker Setup
```bash
# Start PostgreSQL with TimescaleDB
docker run -d \
  --name timescaledb \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=afinewinedynasty \
  timescale/timescaledb:latest-pg15
```

#### Local Installation
```bash
# macOS
brew install postgresql@15
brew install timescaledb

# Ubuntu
sudo apt install postgresql-15 postgresql-15-timescaledb

# Enable TimescaleDB
sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"
```

### Database Migrations

#### Creating Migrations
```bash
cd apps/api

# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add prospect statistics table"

# Create empty migration
alembic revision -m "Custom migration description"
```

#### Running Migrations
```bash
# Upgrade to latest
alembic upgrade head

# Upgrade to specific revision
alembic upgrade +1

# Downgrade
alembic downgrade -1

# View current revision
alembic current

# View migration history
alembic history
```

### Database Seeding
```bash
cd apps/api

# Seed with sample data
python scripts/seed_database.py

# Seed specific data
python scripts/seed_database.py --prospects-only
python scripts/seed_database.py --users-only
```

## API Development

### FastAPI Structure
```
apps/api/
├── app/
│   ├── api/
│   │   └── api_v1/
│   │       ├── endpoints/
│   │       │   ├── auth.py
│   │       │   ├── prospects.py
│   │       │   └── subscriptions.py
│   │       └── api.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── database.py
│   ├── models/
│   │   ├── user.py
│   │   └── prospect.py
│   ├── schemas/
│   │   ├── user.py
│   │   └── prospect.py
│   ├── services/
│   │   ├── user_service.py
│   │   └── prospect_service.py
│   └── main.py
├── alembic/
├── tests/
└── requirements.txt
```

### Adding New Endpoints
```python
# apps/api/app/api/api_v1/endpoints/new_feature.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.schemas.new_feature import NewFeatureCreate, NewFeatureResponse

router = APIRouter()

@router.post("/", response_model=NewFeatureResponse)
async def create_feature(
    *,
    db: AsyncSession = Depends(deps.get_db),
    feature_in: NewFeatureCreate,
    current_user: User = Depends(deps.get_current_user)
) -> NewFeatureResponse:
    """
    Create new feature.

    Required permissions: authenticated user
    """
    # Implementation here
    pass
```

### API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/api/v1/openapi.json

## Frontend Development

### Next.js Structure
```
apps/web/
├── src/
│   ├── app/              # App router pages
│   ├── components/       # React components
│   │   ├── ui/          # Base UI components
│   │   ├── prospects/   # Prospect-related components
│   │   └── layout/      # Layout components
│   ├── hooks/           # Custom React hooks
│   ├── lib/             # Utility libraries
│   │   ├── api/        # API client
│   │   └── utils/      # Helper functions
│   ├── styles/          # Global styles
│   └── types/           # TypeScript types
├── public/              # Static assets
├── __tests__/           # Test files
└── package.json
```

### Creating Components
```typescript
// apps/web/src/components/prospects/ProspectCard.tsx
import React from 'react';
import { Card } from '@/components/ui/card';
import { Prospect } from '@/types/prospect';

interface ProspectCardProps {
  prospect: Prospect;
  onSelect?: (prospect: Prospect) => void;
}

export const ProspectCard: React.FC<ProspectCardProps> = ({
  prospect,
  onSelect
}) => {
  return (
    <Card onClick={() => onSelect?.(prospect)}>
      {/* Component implementation */}
    </Card>
  );
};
```

### API Integration
```typescript
// apps/web/src/lib/api/prospects.ts
import { apiClient } from './client';

export const prospectsApi = {
  async getAll(params?: ProspectFilters) {
    return apiClient.get('/prospects', { params });
  },

  async getById(id: string) {
    return apiClient.get(`/prospects/${id}`);
  },

  async search(query: string) {
    return apiClient.get('/prospects/search', {
      params: { q: query }
    });
  }
};
```

## Testing Strategy

### Backend Testing
```bash
cd apps/api

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/api/test_prospects.py

# Run with verbose output
pytest -v

# Run only marked tests
pytest -m "unit"
pytest -m "integration"
```

### Frontend Testing
```bash
cd apps/web

# Run all tests
npm test

# Run in watch mode
npm run test:watch

# Run with coverage
npm run test:coverage

# Run specific test file
npm test ProspectCard.test.tsx

# E2E tests (if configured)
npm run test:e2e
```

### Writing Tests

#### Backend Test Example
```python
# apps/api/tests/api/api_v1/endpoints/test_prospects.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_get_prospects():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/prospects")
    assert response.status_code == 200
    assert "prospects" in response.json()
```

#### Frontend Test Example
```typescript
// apps/web/src/components/__tests__/ProspectCard.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { ProspectCard } from '../ProspectCard';

describe('ProspectCard', () => {
  it('renders prospect information', () => {
    const prospect = {
      id: '1',
      name: 'Test Player',
      team: 'Test Team'
    };

    render(<ProspectCard prospect={prospect} />);

    expect(screen.getByText('Test Player')).toBeInTheDocument();
    expect(screen.getByText('Test Team')).toBeInTheDocument();
  });
});
```

## Debugging Guide

### Backend Debugging

#### Using VS Code
```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "app.main:app",
        "--reload",
        "--host",
        "0.0.0.0",
        "--port",
        "8000"
      ],
      "jinja": true,
      "justMyCode": false,
      "env": {
        "PYTHONPATH": "${workspaceFolder}/apps/api"
      },
      "cwd": "${workspaceFolder}/apps/api"
    }
  ]
}
```

#### Using PyCharm
1. Create new Run Configuration
2. Select "Python"
3. Module: `uvicorn`
4. Parameters: `app.main:app --reload`
5. Working directory: `path/to/apps/api`
6. Environment variables: Load from .env file

### Frontend Debugging

#### Browser DevTools
```javascript
// Add debugger statements
debugger;

// Or use console methods
console.log('Debug data:', data);
console.table(prospects);
console.trace();
```

#### VS Code Debugging
```json
// .vscode/launch.json
{
  "configurations": [
    {
      "name": "Next.js",
      "type": "node",
      "request": "launch",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["run", "dev"],
      "cwd": "${workspaceFolder}/apps/web",
      "console": "integratedTerminal"
    }
  ]
}
```

## Common Development Tasks

### Adding a New Feature

1. **Create database model** (if needed)
```python
# apps/api/app/models/feature.py
```

2. **Create/update migration**
```bash
alembic revision --autogenerate -m "Add feature table"
alembic upgrade head
```

3. **Create API endpoint**
```python
# apps/api/app/api/api_v1/endpoints/feature.py
```

4. **Add to API router**
```python
# apps/api/app/api/api_v1/api.py
api_router.include_router(feature.router, prefix="/feature", tags=["feature"])
```

5. **Create frontend components**
```typescript
// apps/web/src/components/feature/
```

6. **Add frontend pages**
```typescript
// apps/web/src/app/feature/page.tsx
```

7. **Write tests**
```bash
# Backend
pytest tests/api/test_feature.py

# Frontend
npm test feature.test.tsx
```

### Performance Optimization

#### Backend
- Use database indexes
- Implement query pagination
- Add Redis caching
- Use async/await properly
- Profile with cProfile

#### Frontend
- Implement React.memo
- Use lazy loading
- Optimize images
- Enable code splitting
- Use React Query for caching

## IDE Setup

### VS Code Extensions

Essential:
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- ESLint (dbaeumer.vscode-eslint)
- Prettier (esbenp.prettier-vscode)
- TypeScript (ms-vscode.typescript)

Recommended:
- GitLens (eamodio.gitlens)
- Docker (ms-azuretools.vscode-docker)
- Thunder Client (rangav.vscode-thunder-client)
- Database Client (cweijan.vscode-database-client2)

### VS Code Settings
```json
// .vscode/settings.json
{
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  },
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter"
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  }
}
```

## Troubleshooting

### Common Issues

#### Port Already in Use
```bash
# Find process using port
lsof -i :3000  # macOS/Linux
netstat -ano | findstr :3000  # Windows

# Kill process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows
```

#### Database Connection Issues
```bash
# Check PostgreSQL status
docker ps | grep postgres
pg_isready -h localhost -p 5432

# Reset database
docker-compose down -v
docker-compose up postgres
```

#### Node Modules Issues
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

#### Python Virtual Environment Issues
```bash
# Recreate virtual environment
deactivate
rm -rf venv
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker Documentation](https://docs.docker.com/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)

---

*Last updated: October 2024*