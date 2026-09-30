FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN pip install --no-cache-dir poetry

# Manifeste et verrou copiés seuls : tant qu'ils ne changent pas,
# Docker réutilise la couche d'installation au lieu de tout réinstaller.
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi --only main --no-root

# Le code vient après, car il change à chaque commit.
COPY app/ ./app/

CMD ["python", "-m", "app.main"]
