# ---- Stage 1: build wheels -------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# psycopg2 needs libpq headers; other requirements are pure wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/
RUN pip wheel --wheel-dir /wheels -r requirements/base.txt

# ---- Stage 2: runtime --------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# GeoDjango runtime libraries (GDAL/GEOS/PROJ) + libpq5 for psycopg2.
# The entrypoint needs the Django admin CLI for the initial superuser.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgdal32 \
        libgeos-c1v5 \
        libproj25 \
        libpq5 \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY requirements/ requirements/
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements/base.txt \
    && rm -rf /wheels

COPY . .

RUN python manage.py collectstatic --noinput --settings=config.settings.prod \
        2>/dev/null || echo "collectstatic deferred to container start (env not available at build time)"

RUN chmod +x deploy/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./deploy/entrypoint.sh"]
