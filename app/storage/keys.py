from datetime import datetime, timezone
from uuid import uuid4


def generate_original_key(file_ext, prefix="", now=None):
    now = now or datetime.now(timezone.utc)
    key = f"originals/{now:%Y}/{now:%m}/{uuid4().hex}.{file_ext}"
    return f"{prefix.strip('/')}/{key}" if prefix else key
