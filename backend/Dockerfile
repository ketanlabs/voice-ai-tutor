# Backend (FastAPI domain/state service)
FROM python:3.13-slim

WORKDIR /app
RUN pip install --no-cache-dir uv

# Install dependencies (incl. dev extras so `make test` can run pytest here).
COPY pyproject.toml ./
COPY src ./src
COPY curriculum ./curriculum
COPY tests ./tests
RUN uv pip install --system --no-cache -e ".[dev]"

EXPOSE 8000

# Factory mode avoids constructing the app (and requiring env) at import time.
CMD ["uvicorn", "backend.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
