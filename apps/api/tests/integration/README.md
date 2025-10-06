# Lineup Integration Tests

## Overview
Comprehensive integration tests for the user lineup management feature, including Google OAuth integration and prospect management.

## Test Coverage

### Lineup CRUD Tests (`test_lineups.py`)
- ✅ **Create Lineup**: Test creating custom lineups with validation
- ✅ **List Lineups**: Test pagination and empty states
- ✅ **Get Lineup**: Test retrieving lineup details with prospects
- ✅ **Update Lineup**: Test modifying lineup metadata
- ✅ **Delete Lineup**: Test lineup deletion with cascade

### Prospect Management Tests
- ✅ **Add Prospect**: Test adding prospects to lineups
- ✅ **Update Prospect**: Test modifying prospect position, rank, notes
- ✅ **Remove Prospect**: Test removing prospects from lineups
- ✅ **Duplicate Prevention**: Test adding same prospect twice fails
- ✅ **Bulk Operations**: Test adding multiple prospects at once

### Authorization Tests
- ✅ **Access Control**: Users can only access their own lineups
- ✅ **Unauthorized Access**: Test 401 responses without auth
- ✅ **Cross-User Prevention**: Users cannot modify others' lineups
- ✅ **Proper 404s**: Non-existent resources return 404

## Running Tests

### Run All Integration Tests
```bash
cd apps/api
pytest tests/integration/test_lineups.py -v
```

### Run Specific Test Class
```bash
pytest tests/integration/test_lineups.py::TestLineupCRUD -v
```

### Run Single Test
```bash
pytest tests/integration/test_lineups.py::TestLineupCRUD::test_create_lineup_success -v
```

### Run with Coverage
```bash
pytest tests/integration/test_lineups.py --cov=app.services.lineup_service --cov-report=html
```

## Test Database

Tests use a separate test database: `{POSTGRES_DB}_test`

The test database is automatically:
1. Created before each test function
2. All tables are created from SQLAlchemy models
3. Cleaned up after each test
4. Dropped at the end of the test session

## Test Fixtures

### `db_session`
Provides a clean database session for each test

### `test_user`
Creates a test user with valid credentials

### `test_user_token`
Generates a JWT token for the test user

### `test_prospect`
Creates a sample prospect for testing

### `async_client`
HTTP client with automatic auth token injection

## Expected Test Results

**Total Tests**: 18
- Lineup CRUD: 9 tests
- Prospect Management: 6 tests
- Authorization: 3 tests

All tests should **PASS** ✅

## Common Issues

### Test Database Connection
Ensure PostgreSQL is running and test database can be created:
```bash
psql -U postgres -c "CREATE DATABASE afinewinedynasty_test;"
```

### Async Event Loop
If you see event loop errors, ensure `pytest-asyncio` is installed:
```bash
pip install pytest-asyncio
```

### Import Errors
Make sure you're in the correct directory:
```bash
cd apps/api
export PYTHONPATH=$PWD:$PYTHONPATH
pytest tests/integration/
```
