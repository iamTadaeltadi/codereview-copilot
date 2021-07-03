FROM node:20.18.3-bookworm-slim AS node

FROM python:3.12.8-slim-bookworm

ENV POETRY_VERSION=2.1.3 \
    PIP_DEFAULT_TIMEOUT=100 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git build-essential libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/bin/npm /usr/local/bin/npm
COPY --from=node /usr/local/bin/npx /usr/local/bin/npx
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules

RUN pip install --no-cache-dir poetry==${POETRY_VERSION} poetry-plugin-export==1.9.0

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir --default-timeout=100 --retries 10 -r services/api/requirements.txt
RUN cd web && npm ci
RUN cd services/agents \
    && poetry config virtualenvs.create false \
    && rm -f poetry.lock \
    && poetry lock \
    && poetry install --no-interaction --no-root

CMD ["bash"]
