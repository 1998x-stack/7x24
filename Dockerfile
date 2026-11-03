FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NEWS24_DATA_DIR=/data

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/news24 ./src/news24
RUN python -m pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 news24 \
    && mkdir -p /data \
    && chown news24:news24 /data

COPY tests/fixtures ./tests/fixtures
USER news24
VOLUME ["/data"]
ENTRYPOINT ["news24"]
CMD ["doctor", "--json"]
