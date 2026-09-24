FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 10001 nettwin \
    && chown -R nettwin:nettwin /app
USER nettwin

# 8000/tcp: REST + WS + dashboard; 5514/udp: external telemetry ingestion
EXPOSE 8000/tcp 5514/udp

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

CMD ["python", "run.py"]
