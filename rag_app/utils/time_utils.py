from datetime import datetime, timezone


def to_utc_isoformat(value: datetime) -> str:
    if value.tzinfo is None:
        utc_value = value.replace(tzinfo=timezone.utc)
    else:
        utc_value = value.astimezone(timezone.utc)
    return utc_value.isoformat().replace("+00:00", "Z")
