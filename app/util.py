def format_duration_from_minutes(minutes: int) -> str:
    if minutes < 0:
        raise ValueError("Minutes must be non-negative")

    total_seconds = minutes * 60

    days, total_seconds = divmod(total_seconds, 86400)
    hours, total_seconds = divmod(total_seconds, 3600)
    mins, seconds = divmod(total_seconds, 60)

    parts = []
    if days:
        parts.append(f"{days} days")
    if hours:
        parts.append(f"{hours} hours")
    if mins:
        parts.append(f"{mins} min")
    if seconds or not parts:
        parts.append(f"{seconds} sec")

    return " ".join(parts)
