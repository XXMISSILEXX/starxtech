# Python 3.12 is the supported production runtime.  Pin this tag to a reviewed
# registry digest during each release; no digest is asserted here without a
# registry verification record.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/home/appuser/.local/bin:${PATH}"

WORKDIR /app

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home --shell /usr/sbin/nologin appuser

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
RUN chmod 0755 /app/docker-entrypoint.sh \
    && mkdir -p /app/tmp /app/storage/uploads \
    && chown -R root:root /app \
    && chown -R appuser:appuser /app/tmp /app/storage

USER appuser

EXPOSE 6655
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:6655/healthz', timeout=5).read()"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
