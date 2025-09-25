# A Fine Wine Dynasty - Development Setup

This guide will help you set up the development environment for A Fine Wine Dynasty.

## Prerequisites

- **Docker** and **Docker Compose** installed
- **Node.js** 18+ (for local development)
- **Python** 3.11+ (for local development)
- **Git**

## Quick Start with Docker

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd afinewinedynasty
   ```

2. **Copy environment files**:
   ```bash
   cp .env.example .env
   cp apps/web/.env.example apps/web/.env.local
   cp apps/api/.env.example apps/api/.env
   ```

3. **Start all services**:
   ```bash
   docker-compose up -d
   ```

4. **Verify services are running**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## Local Development Setup

### Frontend (Next.js)

```bash
cd apps/web
npm install
npm run dev
```

### Backend (FastAPI)

```bash
cd apps/api
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Database Setup

```bash
# Using Docker
docker-compose up postgres -d

# Or install PostgreSQL with TimescaleDB locally
# Follow TimescaleDB installation guide: https://docs.timescale.com/install/
```

## Environment Variables

### Required Variables

- `POSTGRES_PASSWORD`: Database password
- `SECRET_KEY`: JWT secret key (generate a secure one for production)

### Optional Variables

- `MLB_API_KEY`: For MLB data integration
- `FANTRAX_API_KEY`: For Fantrax integration
- `STRIPE_SECRET_KEY`: For payment processing

## Testing

### Frontend Tests
```bash
cd apps/web
npm test
```

### Backend Tests
```bash
cd apps/api
pytest
```

### Full Stack Tests
```bash
docker-compose -f docker-compose.yml -f docker-compose.test.yml up --build --abort-on-container-exit
```

## Troubleshooting

### Common Issues

1. **Port conflicts**: Make sure ports 3000, 8000, 5432, and 6379 are available
2. **Docker permission issues**: Ensure your user is in the docker group (Linux/Mac)
3. **Database connection issues**: Check that PostgreSQL is running and credentials are correct

### Health Checks

- API Health: `curl http://localhost:8000/health`
- Database: `docker-compose exec postgres pg_isready -U postgres`
- Redis: `docker-compose exec redis redis-cli ping`

## Production Deployment

See the GitHub Actions workflows in `.github/workflows/` for automated deployment configuration.

## Project Structure

```
├── apps/
│   ├── web/          # Next.js frontend
│   ├── api/          # FastAPI backend
│   └── ml-pipeline/  # ML services (future)
├── packages/         # Shared packages
├── docs/            # Documentation
└── scripts/         # Utility scripts
```