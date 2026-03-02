# Docker Commands for Live Battlefield

## Services
- **app**: FastAPI application (port 8000)
- **postgres**: PostgreSQL database (port 5432)

## Common Commands

### Start/Stop
- `docker compose up -d` - Start all services
- `docker compose up -d app` - Start only app (db must be running)
- `docker compose down` - Stop all services
- `docker compose restart app` - Restart app service

### Logs
- `docker compose logs app` - View app logs
- `docker compose logs app -f` - Follow app logs in real-time
- `docker compose logs postgres` - View database logs
- `docker compose logs app --tail 50` - View last 50 lines of app logs

### Building
- `docker compose build` - Build all services
- `docker compose build app` - Build only app service
- `docker compose build --no-cache app` - Rebuild without cache

### Database
- `docker compose exec postgres psql -U postgres -d battleship` - Connect to DB CLI
- `docker compose exec -T postgres psql -U postgres -d battleship -c "SQL"` - Run SQL command directly

### Testing
- `uv run --with pytest --with pytest-asyncio -- python -m pytest tests/ -v` - Run tests locally

### Debugging
- `docker compose exec app sh` - Shell into app container
- `docker compose exec postgres sh` - Shell into postgres container
- `docker compose ps` - Show running containers status
- `docker compose exec app python -c "import app; print(app.__file__)"` - Verify app import

## Notes
- Use `docker compose` (not `docker-compose`)
- App requires postgres to be healthy before starting
- Environment variables from `.env` file
- Database persists in named volume `postgres_data`
