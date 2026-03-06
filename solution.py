## Student Name: Ricky Nguyen
## Student ID: 219461201

"""
Task A: Appointment Timeslot Recommender (Stub)

In this lab, you will design and implement an Appointment Slot Recommender using an LLM assistant
as your primary programming collaborator.

You are asked to implement a Python module that recommends available meeting slots within a
defined working window.

The system must:
  • Accept working hours (start and end time).
  • Accept a list of existing busy intervals.
  • Accept a required meeting duration.
  • Accept an optional buffer time between meetings.
  • Optionally restrict suggestions to a candidate time window.
  • Return chronologically ordered appointment slots that satisfy all constraints.

The system must ensure that:
  • Suggested slots fall within working hours.
  • Suggested slots do not overlap busy intervals.
  • Buffer time is respected when evaluating availability.
  • Output ordering is deterministic under identical inputs.

The module must preserve the following invariants:
  • Returned slots must be at least as long as the required duration.
  • No returned slot may violate buffer constraints.
  • The returned list must reflect the current system state.

The system must correctly handle non-trivial scenarios such as:
  • Adjacent busy intervals.
  • Very small gaps between meetings.
  • Buffers eliminating otherwise valid availability.
  • Overlapping or unsorted busy intervals.
  • A meeting duration longer than any available gap.
  • No availability within the working window.

Output:
  The output consists of the next N valid appointment suggestions in chronological order.
  Behavior must be deterministic under ties (if any).

See the lab handout for full requirements.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, time
from typing import List, Optional, Tuple


# ---------------- Data Models ----------------

@dataclass(frozen=True)
class TimeWindow:
    """
    A daily time window.
    Assumption (unless stated otherwise in handout): non-wrapping window where start < end.
    """
    start: time
    end: time


@dataclass(frozen=True)
class BusyInterval:
    """
    A busy interval on the given day.
    Invariant: start < end
    """
    start: time
    end: time


@dataclass(frozen=True)
class Slot:
    """
    A recommended appointment slot.

    start_time is a time-of-day within the working window.
    Deterministic ordering: sort by start_time ascending.
    """
    start_time: time


class InfeasibleSchedule(Exception):
    """Raised when no valid slots can be produced (if required by handout)."""
    pass


# ---------------- Helper Functions ----------------

def _combine(day: date, t: time) -> datetime:
    return datetime.combine(day, t)


def _validate_time_window(window: TimeWindow, name: str) -> None:
    if window.start >= window.end:
        raise ValueError(f"{name}.start must be earlier than {name}.end")


def _validate_busy_intervals(busy_intervals: List[BusyInterval]) -> None:
    for interval in busy_intervals:
        if interval.start >= interval.end:
            raise ValueError("Each busy interval must have start < end")


def _merge_intervals(intervals: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    """
    Merge overlapping or adjacent intervals.
    """
    if not intervals:
        return []

    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]

    for current_start, current_end in intervals[1:]:
        last_start, last_end = merged[-1]

        if current_start <= last_end:
            merged[-1] = (last_start, max(last_end, current_end))
        else:
            merged.append((current_start, current_end))

    return merged


# ---------------- Core Function ----------------

def suggest_slots(
    day: date,
    working_hours: TimeWindow,
    busy_intervals: List[BusyInterval],
    duration: timedelta,
    n: int,
    buffer: timedelta = timedelta(0),
    candidate_window: Optional[TimeWindow] = None
) -> List[Slot]:
    """
    Suggest up to the next n valid appointment slots (start times) for the given day.

    Args:
        day: the calendar day for which to suggest slots.
        working_hours: the allowed working window for meetings (start < end).
        busy_intervals: list of busy time intervals (may be overlapping / unsorted).
        duration: required meeting length (must be > 0).
        n: maximum number of slot suggestions to return (n >= 0).
        buffer: optional buffer time required between meetings (buffer >= 0).
        candidate_window: optional extra restriction on suggestions (must lie within this window too).

    Returns:
        A list of Slot objects, sorted by start_time ascending, deterministic under identical inputs.
        If no suitable time slots are available, return an empty list.

    Notes:
        - Suggested slots must fall within working_hours (and candidate_window if provided).
        - Suggested slots must not overlap busy_intervals, considering buffer time.
        - You are free to choose internal representation; inputs use time-of-day.
        - See lab handout for required slot granularity (e.g., 5-min/15-min steps), if any.
    """

    if duration <= timedelta(0):
        raise ValueError("duration must be greater than 0")
    if n < 0:
        raise ValueError("n must be >= 0")
    if buffer < timedelta(0):
        raise ValueError("buffer must be >= 0")

    _validate_time_window(working_hours, "working_hours")
    _validate_busy_intervals(busy_intervals)

    if candidate_window is not None:
        _validate_time_window(candidate_window, "candidate_window")

    if n == 0:
        return []

    working_start_dt = _combine(day, working_hours.start)
    working_end_dt = _combine(day, working_hours.end)

    # Intersect candidate window with working hours if provided
    active_start_dt = working_start_dt
    active_end_dt = working_end_dt

    if candidate_window is not None:
        candidate_start_dt = _combine(day, candidate_window.start)
        candidate_end_dt = _combine(day, candidate_window.end)

        active_start_dt = max(active_start_dt, candidate_start_dt)
        active_end_dt = min(active_end_dt, candidate_end_dt)

    # No usable window after intersection
    if active_start_dt >= active_end_dt:
        return []

    # Convert busy intervals to datetimes and clip to active window after applying buffer
    buffered_busy: List[Tuple[datetime, datetime]] = []
    for interval in busy_intervals:
        busy_start_dt = _combine(day, interval.start) - buffer
        busy_end_dt = _combine(day, interval.end) + buffer

        clipped_start = max(busy_start_dt, active_start_dt)
        clipped_end = min(busy_end_dt, active_end_dt)

        if clipped_start < clipped_end:
            buffered_busy.append((clipped_start, clipped_end))

    # Merge overlapping or adjacent buffered busy intervals
    merged_busy = _merge_intervals(buffered_busy)

    # Find free gaps
    free_gaps: List[Tuple[datetime, datetime]] = []
    cursor = active_start_dt

    for busy_start, busy_end in merged_busy:
        if cursor < busy_start:
            free_gaps.append((cursor, busy_start))
        cursor = max(cursor, busy_end)

    if cursor < active_end_dt:
        free_gaps.append((cursor, active_end_dt))

    # Generate suggestions
    # Assumption used: a valid suggestion is the earliest start time of a block of exact duration.
    # No extra step granularity was specified in the stub, so suggestions begin at each free gap start.
    results: List[Slot] = []

    for gap_start, gap_end in free_gaps:
        if gap_start + duration <= gap_end:
            results.append(Slot(start_time=gap_start.time()))
            if len(results) == n:
                break

    return results