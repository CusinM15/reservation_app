FROM python:3.11-slim AS builder

WORKDIR /app

# System dependencies for build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

# System dependencies for runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    ca-certificates \
    gnupg \
    tzdata \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fonts-noto-core \
    fonts-noto-color-emoji \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    libthai0 \
    && rm -rf /var/lib/apt/lists/*

# PostgreSQL official repo (for pg_dump 18 — server runs 18.4)
RUN curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql-keyring.gpg] http://apt.postgresql.org/pub/repos/apt trixie-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -m -u 1000 appuser

COPY --from=builder /root/.local /home/appuser/.local
COPY app/ app/
COPY scripts/ scripts/
COPY documentation/ documentation/

RUN chown -R appuser:appuser /app
USER appuser

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PASSLIB_BCRYPT_AVOID_WRAP_BUG=1

# Opomba: VOLUME tu namenoma NI. Railway (in nekateri drugi graditelji) zavrne
# Dockerfile z ukazom VOLUME — tam se trajna shramba nastavi kot Railway Volume.
# Kubernetes ukaz VOLUME tako ali tako ignorira, zato ga ne potrebujemo: /tmp je
# v vsebniku običajna mapa z dovoljenjem za pisanje (uporablja jo npr. --save
# pri varnostnih kopijah).
EXPOSE 8002

# workers=1 — dovolj za obremenitev šole; PostgreSQL podpira več
# workerjev, če bo kdaj potrebno povečati.
# Vrata: privzeto 8002 (k3s/Docker), če pa okolje nastavi PORT (Railway,
# Heroku, drugi PaaS), poslušamo tam — sicer promet ne pride do aplikacije.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8002} --workers 1"]
