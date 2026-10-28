from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC datetime (portable across SQLite/PostgreSQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat() + "Z"
