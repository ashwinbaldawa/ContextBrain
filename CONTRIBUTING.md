# Contributing to APIBrain

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

1. Fork and clone the repo
2. Create a virtual environment: `python -m venv .venv && source .venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and configure
5. Start PostgreSQL with pgvector (Docker recommended: `docker compose up db`)
6. Initialize the database: `python scripts/init_db.py`
7. Run the server: `uvicorn src.main:app --reload`

## Adding Sample API Specs

Drop OpenAPI 3.x JSON files into `sample_specs/` and add an entry in `scripts/seed_sample_apis.py`.

## Running Tests

```bash
pytest tests/ -v
```

## Pull Request Process

1. Create a feature branch from `main`
2. Write tests for new functionality
3. Ensure all tests pass
4. Update documentation if needed
5. Submit a PR with a clear description

## Code Style

- Python: Follow PEP 8, use type hints
- Use `async/await` for all database and API operations
- Keep functions focused and well-documented
