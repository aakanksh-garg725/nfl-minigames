from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")


def utcnow() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime) -> datetime:
    # SQLite drops timezone metadata; persisted values are always UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def weekly_window(sunday: date) -> tuple[datetime, datetime]:
    if sunday.weekday() != 6:
        raise ValueError("Weekly deadline must be a Sunday")
    opens = datetime.combine(sunday - timedelta(days=5), time(9), EASTERN)
    closes = datetime.combine(sunday, time(13), EASTERN)
    return opens.astimezone(UTC), closes.astimezone(UTC)
