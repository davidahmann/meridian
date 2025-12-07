from meridian.events import AxiomEvent


def test_axiom_event_creation() -> None:
    event = AxiomEvent(event_type="test", entity_id="u1", payload={"foo": "bar"})
    assert event.id is not None
    assert event.timestamp is not None
    assert event.event_type == "test"
    assert event.payload == {"foo": "bar"}
