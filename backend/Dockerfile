FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY current_env.txt ./current_env.txt
RUN pip install --upgrade pip && pip install -r current_env.txt

COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

RUN addgroup --system comptaflow \
    && adduser --system --ingroup comptaflow comptaflow \
    && mkdir -p /app/storage_local \
    && chown -R comptaflow:comptaflow /app

USER comptaflow
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
