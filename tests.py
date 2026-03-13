import pytest
from datetime import date, datetime, time, timedelta

from solution import (
    BusyInterval,
    NoValidSlotError,
    Slot,
    TimeWindow,
    suggest_slots,
    suggest_slots_with_explanation,
)


def combine(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


# Covers C2, AC2
def test_slots_do_not_overlap_busy_intervals():
    day = date(2026, 3, 12)
    working_hours = TimeWindow(start=time(9, 0), end=time(17, 0))
    busy_intervals = [
        BusyInterval(
            start=combine(day, time(10, 0)),
            end=combine(day, time(11, 0)),
        )
    ]

    slots = suggest_slots(
        day=day,
        working_hours=working_hours,
        busy_intervals=busy_intervals,
        duration=timedelta(minutes=30),
        n=5,
        buffer=timedelta(minutes=0),
    )

    assert len(slots) > 0
    for slot in slots:
        assert slot.end <= combine(day, time(10, 0)) or slot.start >= combine(day, time(11, 0))


# Covers C1, C4, AC1, AC3
def test_same_input_produces_same_output_in_same_order():
    day = date(2026, 3, 12)
    working_hours = TimeWindow(start=time(9, 0), end=time(17, 0))
    busy_intervals = [
        BusyInterval(
            start=combine(day, time(12, 0)),
            end=combine(day, time(13, 0)),
        )
    ]

    slots_run_1 = suggest_slots(
        day=day,
        working_hours=working_hours,
        busy_intervals=busy_intervals,
        duration=timedelta(minutes=30),
        n=4,
        buffer=timedelta(minutes=0),
    )

    slots_run_2 = suggest_slots(
        day=day,
        working_hours=working_hours,
        busy_intervals=busy_intervals,
        duration=timedelta(minutes=30),
        n=4,
        buffer=timedelta(minutes=0),
    )

    assert slots_run_1 == slots_run_2


# Covers C3, AC5
def test_no_duplicate_slots_returned():
    day = date(2026, 3, 12)
    working_hours = TimeWindow(start=time(9, 0), end=time(12, 0))

    # Overlapping busy intervals could create duplicate processing paths
    busy_intervals = [
        BusyInterval(
            start=combine(day, time(9, 30)),
            end=combine(day, time(10, 0)),
        ),
        BusyInterval(
            start=combine(day, time(9, 45)),
            end=combine(day, time(10, 15)),
        ),
    ]

    slots = suggest_slots(
        day=day,
        working_hours=working_hours,
        busy_intervals=busy_intervals,
        duration=timedelta(minutes=30),
        n=10,
        buffer=timedelta(minutes=0),
    )

    unique_pairs = {(slot.start, slot.end) for slot in slots}
    assert len(slots) == len(unique_pairs)


# Covers C5, C6, AC4
def test_explicit_explanation_when_no_valid_slot_exists():
    day = date(2026, 3, 12)
    working_hours = TimeWindow(start=time(9, 0), end=time(10, 0))
    busy_intervals = [
        BusyInterval(
            start=combine(day, time(9, 0)),
            end=combine(day, time(10, 0)),
        )
    ]

    result = suggest_slots_with_explanation(
        day=day,
        working_hours=working_hours,
        busy_intervals=busy_intervals,
        duration=timedelta(minutes=30),
        n=3,
        buffer=timedelta(minutes=0),
    )

    assert result.slots == []
    assert result.explanation is not None
    assert "No valid slot is available" in result.explanation


# Covers C2, AC6
def test_slots_respect_duration_and_buffer():
    day = date(2026, 3, 12)
    working_hours = TimeWindow(start=time(9, 0), end=time(12, 0))
    busy_intervals = [
        BusyInterval(
            start=combine(day, time(10, 0)),
            end=combine(day, time(10, 30)),
        )
    ]

    slots = suggest_slots(
        day=day,
        working_hours=working_hours,
        busy_intervals=busy_intervals,
        duration=timedelta(minutes=30),
        n=10,
        buffer=timedelta(minutes=15),
    )

    assert len(slots) > 0
    for slot in slots:
        assert slot.end - slot.start == timedelta(minutes=30)
        assert slot.end <= combine(day, time(9, 45)) or slot.start >= combine(day, time(10, 45))


# Covers C2, C5, C6, AC4, AC6
def test_no_slot_when_buffer_eliminates_remaining_free_time():
    day = date(2026, 3, 12)
    working_hours = TimeWindow(start=time(9, 0), end=time(10, 0))
    busy_intervals = [
        BusyInterval(
            start=combine(day, time(9, 20)),
            end=combine(day, time(9, 40)),
        )
    ]

    result = suggest_slots_with_explanation(
        day=day,
        working_hours=working_hours,
        busy_intervals=busy_intervals,
        duration=timedelta(minutes=20),
        n=2,
        buffer=timedelta(minutes=10),
    )

    assert result.slots == []
    assert result.explanation is not None


# Covers C2, C6, AC4
def test_candidate_window_outside_working_hours_returns_explanation():
    day = date(2026, 3, 12)
    working_hours = TimeWindow(start=time(9, 0), end=time(17, 0))
    candidate_window = TimeWindow(start=time(18, 0), end=time(19, 0))

    result = suggest_slots_with_explanation(
        day=day,
        working_hours=working_hours,
        busy_intervals=[],
        duration=timedelta(minutes=30),
        n=3,
        buffer=timedelta(minutes=0),
        candidate_window=candidate_window,
    )

    assert result.slots == []
    assert result.explanation is not None
    assert "candidate window" in result.explanation.lower()


# Covers C2, C3, AC2, AC5
def test_returns_no_more_than_requested_number_of_slots():
    day = date(2026, 3, 12)
    working_hours = TimeWindow(start=time(9, 0), end=time(17, 0))

    slots = suggest_slots(
        day=day,
        working_hours=working_hours,
        busy_intervals=[],
        duration=timedelta(minutes=30),
        n=2,
        buffer=timedelta(minutes=0),
    )

    assert len(slots) == 2


# Covers C5, C6, AC4
def test_suggest_slots_raises_error_when_no_valid_slot_exists():
    day = date(2026, 3, 12)
    working_hours = TimeWindow(start=time(9, 0), end=time(9, 20))

    with pytest.raises(NoValidSlotError) as exc_info:
        suggest_slots(
            day=day,
            working_hours=working_hours,
            busy_intervals=[],
            duration=timedelta(minutes=30),
            n=1,
            buffer=timedelta(minutes=0),
        )

    assert "No valid slot is available" in str(exc_info.value)