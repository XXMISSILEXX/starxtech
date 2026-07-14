# Pinned to the digest validated by the production build for reproducibility.
FROM python:3.10-slim@sha256:032f5a6e4684899c16735305a83c2a8b1849724b4b6976083ead9aca0846ceb0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/home/appuser/.local/bin:${PATH}"

WORKDIR /app

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/storage/uploads /app/tmp \
    && chown -R appuser:appuser /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . /app
RUN chmod 0755 /app/docker-entrypoint.sh

USER appuser

EXPOSE 6655

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
