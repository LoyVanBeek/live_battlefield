# Plan: Add CI (Continuous Integration)

## Overview
Set up GitHub Actions workflow to automatically run tests, linting, and type checking on every push and pull request.

## References
- Original TODO: docs/TODO.md item 47

## Current State
- No CI pipeline
- Manual testing and linting

## Implementation Plan

### Step 1: Create GitHub Actions workflow directory
```bash
mkdir -p .github/workflows
```

### Step 2: Create CI workflow file
Create `.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

env:
  PYTHON_VERSION: '3.11'

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install ruff
      
      - name: Run ruff (linter)
        run: ruff check .
      
      - name: Run ruff (formatter check)
        run: ruff format --check .

  typecheck:
    name: Type Check
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install mypy types-python-telegram-bot types-requests
      
      - name: Install project dependencies
        run: |
          pip install -e .
        env:
          TELEGRAM_BOT_TOKEN: dummy
      
      - name: Run mypy
        run: mypy app/

  test:
    name: Test
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: battleship_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pytest pytest-asyncio httpx
      
      - name: Install project dependencies
        run: |
          pip install -e .
        env:
          TELEGRAM_BOT_TOKEN: dummy
      
      - name: Create .env file
        run: |
          echo "TELEGRAM_BOT_TOKEN=test_token" > .env
          echo "DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/battleship_test" >> .env
      
      - name: Run database migrations
        run: alembic upgrade head
      
      - name: Run tests
        run: pytest tests/ -v

  build:
    name: Build Docker
    runs-on: ubuntu-latest
    needs: [lint, typecheck, test]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Build Docker image
        run: docker build .
      
      - name: Build docker-compose
        run: docker compose build
```

### Step 3: Add pytest configuration
Create `pytest.ini` or add to `pyproject.toml`:
```ini
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
addopts = "-v --tb=short"
filterwarnings = [
    "ignore::DeprecationWarning",
]
```

### Step 4: Add mypy configuration
Create or update `mypy.ini`:
```ini
[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
ignore_missing_imports = True

[mypy-telegram.*]
ignore_missing_imports = True

[mypy-tests.*]
disallow_untyped_defs = False
```

### Step 5: Add ruff configuration
Update `pyproject.toml`:
```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "C4", "SIM"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"
```

### Step 6: Add GitHub token for CI (optional for PR builds)
No additional setup needed for public repos.

### Step 7: Create test database fixture
Ensure tests use test database:
```python
# tests/conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.database import Base

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/battleship_test"

@pytest.fixture(scope="session")
def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    return engine

@pytest.fixture(scope="function")
async def test_db(test_engine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

### Step 8: Badge for README
Add CI badge to README.md:
```markdown
[![CI](https://github.com/username/live_battlefield/actions/workflows/ci.yml/badge.svg)](https://github.com/username/live_battlefield/actions/workflows/ci.yml)
```

## Files to Create
1. `.github/workflows/ci.yml`
2. `pytest.ini` or add to `pyproject.toml`
3. `mypy.ini` (optional, can be in pyproject.toml)

## Files to Modify
1. `pyproject.toml` - Add pytest, mypy, ruff config
2. `README.md` - Add CI badge

## Workflow Summary

| Job | Tool | What it does |
|-----|------|--------------|
| lint | ruff | Check code style, import order, common errors |
| typecheck | mypy | Type checking |
| test | pytest | Run all tests with test DB |
| build | docker | Verify Dockerfile builds |

## Optional Enhancements

### Security Scanning
```yaml
  security:
    name: Security
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run bandit
        run: pip install bandit && bandit -r app/
```

### Docker Hub Push
```yaml
  push:
    name: Push to Registry
    runs-on: ubuntu-latest
    if: github.event_name == 'push'
    steps:
      - uses: actions/checkout@v4
      - name: Push to Docker Hub
        # Add Docker Hub push steps
```

## Testing
1. Push to a branch and verify CI runs
2. Verify all jobs pass
3. Create a PR and verify checks appear
4. Introduce a lint error and verify CI fails
