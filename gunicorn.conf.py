import os

bind = f"0.0.0.0:{os.getenv('APP_PORT', '6655')}"

workers = int(os.getenv("WEB_CONCURRENCY", "2"))
worker_tmp_dir = "/app/tmp"
threads = int(os.getenv("GUNICORN_THREADS", "2"))

worker_class = "gthread"
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
