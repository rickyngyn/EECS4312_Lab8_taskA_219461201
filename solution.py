from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import List, Optional


class NoValidSlotError(ValueError):
    """Raised when no valid slot can be generated."""

    pass


@dataclass(frozen=True, order=True)
class TimeWindow:
    start: time
    end: time

    def validate(self) -> None:
        if self.start >= self.end:
            raise ValueError("TimeWindow start must be earlier than end.")


@dataclass(frozen=True, order=True)
class BusyInterval:
    start: datetime
    end: datetime

    def validate(self) -> None:
        if self.start >= self.end:
            raise ValueError("BusyInterval start must be earlier than end.")


@dataclass(frozen=True, order=True)
class Slot:
    start: datetime
    end: datetime

    def validate(self) -> None:
        if self.start >= self.end:
            raise ValueError("Slot start must be earlier than end.")


@dataclass(frozen=True)
class SuggestionResult:
    slots: List[Slot]
    explanation: Optional[str] = None


def suggest_slots(
    day: date,
    working_hours: TimeWindow,
    busy_intervals: List[BusyInterval],
    duration: timedelta,
    n: int,
    buffer: timedelta = timedelta(0),
    candidate_window: Optional[TimeWindow] = None,
    explain_on_failure: bool = False,
) -> List[Slot]:
    """
    Returns up to n valid suggested slots.

    If explain_on_failure is False and no valid slot exists, a NoValidSlotError is raised.
    If explain_on_failure is True and no valid slot exists, an empty list is returned.
    """

    result = suggest_slots_with_explanation(
        day=day,
        working_hours=working_hours,
        busy_intervals=busy_intervals,
        duration=duration,
        n=n,
        buffer=buffer,
        candidate_window=candidate_window,
    )

    if result.slots:
        return result.slots

    if explain_on_failure:
        return []

    raise NoValidSlotError(result.explanation or "No valid slot is available.")


def suggest_slots_with_explanation(
    day: date,
    working_hours: TimeWindow,
    busy_intervals: List[BusyInterval],
    duration: timedelta,
    n: int,
    buffer: timedelta = timedelta(0),
    candidate_window: Optional[TimeWindow] = None,
) -> SuggestionResult:
    """
    Returns a SuggestionResult containing:
    1. a deterministic list of valid slots
    2. an explicit explanation if no slot can be generated
    """

    _validate_inputs(
        day=day,
        working_hours=working_hours,
        busy_intervals=busy_intervals,
        duration=duration,
        n=n,
        buffer=buffer,
        candidate_window=candidate_window,
    )

    effective_window = _get_effective_window(day, working_hours, candidate_window)
    if effective_window is None:
        return SuggestionResult(
            slots=[],
            explanation=(
                "No valid slot is available because the candidate window does not "
                "overlap with working hours."
            ),
        )

    blocked = _normalize_busy_intervals(
        day=day,
        busy_intervals=busy_intervals,
        effective_start=effective_window.start,
        effective_end=effective_window.end,
        buffer=buffer,
    )

    free_intervals = _compute_free_intervals(
        effective_start=effective_window.start,
        effective_end=effective_window.end,
        blocked=blocked,
    )

    slots: List[Slot] = []
    for free_start, free_end in free_intervals:
        current_start = free_start
        while current_start + duration <= free_end:
            current_end = current_start + duration
            slots.append(Slot(start=current_start, end=current_end))
            current_start = current_end
    slots = _deduplicate_and_sort_slots(slots)

    if n == 0:
        return SuggestionResult(slots=[])

    slots = slots[:n]

    if slots:
        return SuggestionResult(slots=slots)

    return SuggestionResult(
        slots=[],
        explanation=_build_no_slot_explanation(
            effective_window=effective_window,
            blocked=blocked,
            duration=duration,
            buffer=buffer,
        ),
    )


def _validate_inputs(
    day: date,
    working_hours: TimeWindow,
    busy_intervals: List[BusyInterval],
    duration: timedelta,
    n: int,
    buffer: timedelta,
    candidate_window: Optional[TimeWindow],
) -> None:
    if not isinstance(day, date):
        raise ValueError("day must be a valid date.")

    working_hours.validate()

    if candidate_window is not None:
        candidate_window.validate()

    if duration <= timedelta(0):
        raise ValueError("duration must be greater than zero.")

    if buffer < timedelta(0):
        raise ValueError("buffer must be non negative.")

    if n < 0:
        raise ValueError("n must be non negative.")

    for interval in busy_intervals:
        interval.validate()


def _get_effective_window(
    day: date,
    working_hours: TimeWindow,
    candidate_window: Optional[TimeWindow],
) -> Optional[BusyInterval]:
    work_start = datetime.combine(day, working_hours.start)
    work_end = datetime.combine(day, working_hours.end)

    if candidate_window is None:
        return BusyInterval(start=work_start, end=work_end)

    candidate_start = datetime.combine(day, candidate_window.start)
    candidate_end = datetime.combine(day, candidate_window.end)

    effective_start = max(work_start, candidate_start)
    effective_end = min(work_end, candidate_end)

    if effective_start >= effective_end:
        return None

    return BusyInterval(start=effective_start, end=effective_end)


def _normalize_busy_intervals(
    day: date,
    busy_intervals: List[BusyInterval],
    effective_start: datetime,
    effective_end: datetime,
    buffer: timedelta,
) -> List[BusyInterval]:
    same_day_intervals: List[BusyInterval] = []

    for interval in busy_intervals:
        if interval.end.date() < day or interval.start.date() > day:
            continue

        start = interval.start - buffer
        end = interval.end + buffer

        start = max(start, effective_start)
        end = min(end, effective_end)

        if start < end:
            same_day_intervals.append(BusyInterval(start=start, end=end))

    return _merge_intervals(sorted(same_day_intervals, key=lambda x: (x.start, x.end)))


def _merge_intervals(intervals: List[BusyInterval]) -> List[BusyInterval]:
    if not intervals:
        return []

    merged: List[BusyInterval] = [intervals[0]]

    for current in intervals[1:]:
        last = merged[-1]
        if current.start <= last.end:
            merged[-1] = BusyInterval(
                start=last.start,
                end=max(last.end, current.end),
            )
        else:
            merged.append(current)

    return merged


def _compute_free_intervals(
    effective_start: datetime,
    effective_end: datetime,
    blocked: List[BusyInterval],
) -> List[tuple[datetime, datetime]]:
    free: List[tuple[datetime, datetime]] = []
    cursor = effective_start

    for interval in blocked:
        if cursor < interval.start:
            free.append((cursor, interval.start))
        cursor = max(cursor, interval.end)

    if cursor < effective_end:
        free.append((cursor, effective_end))

    return free


def _deduplicate_and_sort_slots(slots: List[Slot]) -> List[Slot]:
    unique = {(slot.start, slot.end): slot for slot in slots}
    return sorted(unique.values(), key=lambda s: (s.start, s.end))


def _build_no_slot_explanation(
    effective_window: BusyInterval,
    blocked: List[BusyInterval],
    duration: timedelta,
    buffer: timedelta,
) -> str:
    total_window = effective_window.end - effective_window.start

    if total_window < duration:
        return (
            "No valid slot is available because the available time window is shorter "
            "than the requested duration."
        )

    if blocked:
        return (
            "No valid slot is available because existing busy intervals and buffer "
            "requirements leave insufficient free time."
        )

    return (
        "No valid slot is available because the request cannot be satisfied under "
        "the current scheduling constraints."
    )