"""
Availability checking: weekly hours + existing bookings + buffer + daily cap.

Times coming in/out of this module are timezone-aware. The voice config
carries a tz string (IANA); we interpret business hours in that tz, then
compare against bookings stored as UTC in the DB.
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python 3.8 fallback — unlikely here, but safe
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

from app.features.voice import repository as repo


_DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _day_key_for(d: date) -> str:
    return _DAY_KEYS[d.weekday()]


def _parse_hhmm(s: str) -> time:
    return time.fromisoformat(s)


def _day_window(
    weekly_hours: Dict[str, Any],
    target_day: date,
    tz: ZoneInfo,
) -> Optional[Tuple[datetime, datetime]]:
    entry = weekly_hours.get(_day_key_for(target_day))
    if not entry or not entry.get("enabled"):
        return None
    open_t = _parse_hhmm(entry["open"])
    close_t = _parse_hhmm(entry["close"])
    start = datetime.combine(target_day, open_t, tzinfo=tz)
    end = datetime.combine(target_day, close_t, tzinfo=tz)
    if end <= start:
        return None
    return start, end


def generate_slots(
    availability: Dict[str, Any],
    tz_name: str,
    day: date,
    duration_minutes: int,
    existing_bookings: List[Dict[str, Any]],
) -> List[Tuple[datetime, datetime]]:
    """Free slots for a given local date, honoring granularity, buffer, and cap."""
    tz = ZoneInfo(tz_name)
    window = _day_window(availability["weekly_hours"], day, tz)
    if window is None:
        return []
    open_dt, close_dt = window

    granularity = max(5, int(availability["slot_granularity_minutes"]))
    buffer_m = max(0, int(availability["buffer_minutes"]))
    daily_cap = max(1, int(availability["daily_cap"]))
    duration = timedelta(minutes=duration_minutes)
    buffer = timedelta(minutes=buffer_m)

    booked_ranges: List[Tuple[datetime, datetime]] = []
    for b in existing_bookings:
        if b.get("status") in ("cancelled",):
            continue
        s = datetime.fromisoformat(b["starts_at"].replace("Z", "+00:00")).astimezone(tz)
        e = datetime.fromisoformat(b["ends_at"].replace("Z", "+00:00")).astimezone(tz)
        booked_ranges.append((s - buffer, e + buffer))
    active_count = sum(1 for b in existing_bookings if b.get("status") != "cancelled")
    if active_count >= daily_cap:
        return []

    slots: List[Tuple[datetime, datetime]] = []
    cursor = open_dt
    while cursor + duration <= close_dt:
        slot_end = cursor + duration
        conflict = any(not (slot_end <= bs or cursor >= be) for bs, be in booked_ranges)
        if not conflict:
            slots.append((cursor, slot_end))
        cursor += timedelta(minutes=granularity)
    return slots


def next_available_slots(
    company_id: str,
    duration_minutes: int,
    *,
    after: Optional[datetime] = None,
    max_results: int = 5,
    lookahead_days: int = 14,
) -> List[Dict[str, Any]]:
    """Look forward up to `lookahead_days` and return up to `max_results` free slots."""
    config = repo.get_or_create_voice_config(company_id)
    availability = repo.get_or_create_availability(company_id)
    tz_name = config.get("timezone") or "America/New_York"
    tz = ZoneInfo(tz_name)

    start_dt = (after or datetime.now(timezone.utc)).astimezone(tz)
    results: List[Dict[str, Any]] = []

    for offset in range(lookahead_days):
        target_day = (start_dt + timedelta(days=offset)).date()
        day_start = datetime.combine(target_day, time.min, tzinfo=tz)
        day_end = datetime.combine(target_day + timedelta(days=1), time.min, tzinfo=tz)
        bookings = repo.list_bookings_in_range(
            company_id,
            day_start.astimezone(timezone.utc),
            day_end.astimezone(timezone.utc),
            exclude_statuses=["cancelled"],
        )
        slots = generate_slots(availability, tz_name, target_day, duration_minutes, bookings)
        for s, e in slots:
            if s < start_dt:
                continue
            results.append(
                {
                    "start_local": s.isoformat(),
                    "end_local": e.isoformat(),
                    "start_utc": s.astimezone(timezone.utc).isoformat(),
                    "end_utc": e.astimezone(timezone.utc).isoformat(),
                    "timezone": tz_name,
                }
            )
            if len(results) >= max_results:
                return results
    return results


def is_slot_free(company_id: str, start_utc: datetime, end_utc: datetime) -> bool:
    """Re-check a slot right before creating a booking (race-safe enough for single worker)."""
    config = repo.get_or_create_voice_config(company_id)
    availability = repo.get_or_create_availability(company_id)
    tz = ZoneInfo(config.get("timezone") or "America/New_York")
    start_local = start_utc.astimezone(tz)
    end_local = end_utc.astimezone(tz)
    if start_local.date() != end_local.date():
        return False

    window = _day_window(availability["weekly_hours"], start_local.date(), tz)
    if window is None:
        return False
    open_dt, close_dt = window
    if start_local < open_dt or end_local > close_dt:
        return False

    day_start = datetime.combine(start_local.date(), time.min, tzinfo=tz)
    day_end = datetime.combine(start_local.date() + timedelta(days=1), time.min, tzinfo=tz)
    bookings = repo.list_bookings_in_range(
        company_id,
        day_start.astimezone(timezone.utc),
        day_end.astimezone(timezone.utc),
        exclude_statuses=["cancelled"],
    )
    if len(bookings) >= int(availability["daily_cap"]):
        return False

    buffer = timedelta(minutes=int(availability["buffer_minutes"]))
    for b in bookings:
        bs = datetime.fromisoformat(b["starts_at"].replace("Z", "+00:00"))
        be = datetime.fromisoformat(b["ends_at"].replace("Z", "+00:00"))
        if not (end_utc <= bs - buffer or start_utc >= be + buffer):
            return False
    return True
