"""Deterministic relative-date helpers for fallback understanding only."""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

_WORD_NUMBERS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
}

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_MONTH_DAY = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?\b",
    re.IGNORECASE,
)
_DAYS = re.compile(
    r"\b(?:(\d+)|(" + "|".join(_WORD_NUMBERS) + r"))\s+days?\b",
    re.IGNORECASE,
)
_THROUGH = re.compile(
    r"\b(" + "|".join(_WEEKDAYS) + r")\s+(?:through|to|until|-)\s+("
    + "|".join(_WEEKDAYS)
    + r")\b",
    re.IGNORECASE,
)
_AND_DAYS = re.compile(
    r"\b(" + "|".join(_WEEKDAYS) + r")\s+and\s+(" + "|".join(_WEEKDAYS) + r")\b",
    re.IGNORECASE,
)


def reference_today() -> date:
    return date.today()


def parse_duration_days(text: str) -> int | None:
    match = _DAYS.search(text)
    if not match:
        return None
    if match.group(1):
        return int(match.group(1))
    return _WORD_NUMBERS.get(match.group(2).lower())


def _next_weekday(today: date, weekday: int) -> date:
    delta = (weekday - today.weekday()) % 7
    return today + timedelta(days=delta)


def _next_week_monday(today: date) -> date:
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    return today + timedelta(days=days_until_monday)


def extract_dates(text: str, *, today: date | None = None) -> tuple[list[str], str | None, str | None, int | None]:
    """Return (dates, start_date, end_date, inferred_duration). Never invents missing dates."""

    now = today or reference_today()
    lowered = text.lower()
    dates: list[str] = []

    for match in _ISO_DATE.findall(text):
        dates.append(match)

    for match in _MONTH_DAY.finditer(text):
        month_name = match.group(1).title()
        day = int(match.group(2))
        year = int(match.group(3)) if match.group(3) else now.year
        month = list(calendar.month_name).index(month_name)
        try:
            parsed = date(year, month, day)
        except ValueError:
            continue
        iso = parsed.isoformat()
        if iso not in dates:
            dates.append(iso)

    through = _THROUGH.search(lowered) or _AND_DAYS.search(lowered)
    if through:
        start = _next_weekday(now, _WEEKDAYS[through.group(1).lower()])
        end = _next_weekday(now, _WEEKDAYS[through.group(2).lower()])
        if end < start:
            end = end + timedelta(days=7)
        span = [(start + timedelta(days=offset)).isoformat() for offset in range((end - start).days + 1)]
        for item in span:
            if item not in dates:
                dates.append(item)

    if re.search(r"\b(next\s+)?friday\b", lowered) and "through" not in lowered and " and " not in lowered:
        friday = _next_weekday(now, 4)
        if friday.isoformat() not in dates:
            dates.append(friday.isoformat())

    duration = parse_duration_days(text)
    start: str | None = dates[0] if dates else None
    end: str | None = dates[-1] if len(dates) > 1 else None

    if "next week" in lowered and start is None:
        start_date = _next_week_monday(now)
        start = start_date.isoformat()
        if duration:
            end_date = start_date + timedelta(days=duration - 1)
            end = end_date.isoformat()
            dates = [
                (start_date + timedelta(days=offset)).isoformat()
                for offset in range(duration)
            ]
        else:
            dates = [start]

    if start and end and duration is None:
        try:
            duration = (
                date.fromisoformat(end) - date.fromisoformat(start)
            ).days + 1
        except ValueError:
            duration = None
    elif start and duration and not end:
        try:
            end = (date.fromisoformat(start) + timedelta(days=duration - 1)).isoformat()
        except ValueError:
            end = None

    return dates, start, end, duration
