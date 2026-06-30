from pathlib import Path

from pr_repair.logging import log_event
from pr_repair.telemetry.trace import TraceRecorder


def test_recorder_captures_events_in_order() -> None:
    with TraceRecorder() as recorder:
        log_event("first", a=1)
        log_event("second", b="x")

    events = recorder.events()
    assert [e.seq for e in events] == [1, 2]
    assert [e.event for e in events] == ["first", "second"]
    assert events[0].fields == {"a": 1}
    assert events[1].fields == {"b": "x"}


def test_recorder_stops_capturing_after_context() -> None:
    recorder = TraceRecorder()
    with recorder:
        log_event("inside")
    log_event("outside")

    assert [e.event for e in recorder.events()] == ["inside"]


def test_recorder_json_safe_coerces_complex_values() -> None:
    with TraceRecorder() as recorder:
        log_event("paths", target=Path("/tmp/x"), rules=["a", "b"], obj={"k": "v"})

    fields = recorder.events()[0].fields
    assert fields["target"] == "/tmp/x"
    assert fields["rules"] == ["a", "b"]
    assert isinstance(fields["obj"], str)


def test_to_list_is_json_serializable() -> None:
    with TraceRecorder() as recorder:
        log_event("e", n=1)
    dumped = recorder.to_list()
    assert dumped == [{"seq": 1, "event": "e", "fields": {"n": 1}}]


def test_nested_recorders_are_independent() -> None:
    outer = TraceRecorder()
    inner = TraceRecorder()
    with outer:
        log_event("a")
        with inner:
            log_event("b")
        log_event("c")

    assert [e.event for e in outer.events()] == ["a", "b", "c"]
    assert [e.event for e in inner.events()] == ["b"]
