"""Off-limit zone enforcement in the sim (Amendment A3).

A goto into a zone is refused with a ``flight.refused`` event; route
planning drops zone waypoints; the geometry helpers stay honest.
"""

from __future__ import annotations

from meemoo.core import topics
from meemoo.flight.sim_blimp import FlightMode, SimulatedBlimp
from meemoo.flight.zones import Zone, split_route, zone_containing

BATHROOM = Zone("the bathroom", 7.0, 0.0, 2.0, 3.0)


def test_zone_contains_edges() -> None:
    assert BATHROOM.contains(7.0, 0.0)
    assert BATHROOM.contains(9.0, 3.0)
    assert BATHROOM.contains(8.0, 1.5)
    assert not BATHROOM.contains(6.9, 1.5)
    assert not BATHROOM.contains(8.0, 3.1)


def test_zone_containing_picks_first_match() -> None:
    other = Zone("bedroom corner", 7.5, 1.0, 1.0, 1.0)
    assert zone_containing([BATHROOM, other], 8.0, 1.5) is BATHROOM
    assert zone_containing([other, BATHROOM], 8.0, 1.5) is other
    assert zone_containing([BATHROOM], 1.0, 1.0) is None


def test_split_route_partitions() -> None:
    wps = [
        ("living room", "area", 2.8, 2.2),
        ("bathroom sink", "area", 8.0, 1.5),
        ("kitchen", "area", 5.6, 1.6),
    ]
    allowed, refusals = split_route([BATHROOM], 1, wps)
    assert [w[0] for w in allowed] == ["living room", "kitchen"]
    assert len(refusals) == 1
    assert refusals[0]["zone"] == "the bathroom"
    assert refusals[0]["label"] == "bathroom sink"


def test_goto_into_zone_refused() -> None:
    sim = SimulatedBlimp("apartment", seed=3)
    sim.set_no_go_zones([BATHROOM])
    assert sim.mode is FlightMode.DOCKED
    accepted = sim.goto(8.0, 1.5, label="bathroom")
    assert accepted is False
    assert sim.mode is FlightMode.DOCKED  # never started the flight
    emissions = sim.tick(0.02)
    refused = [p for t, p in emissions if t == topics.FLIGHT_REFUSED]
    assert len(refused) == 1
    assert refused[0]["zone"] == "the bathroom"
    assert "off limits" in str(refused[0]["reason"])
    # refusal is emitted once, not every tick
    assert not [t for t, _ in sim.tick(0.02) if t == topics.FLIGHT_REFUSED]


def test_goto_outside_zone_accepted() -> None:
    sim = SimulatedBlimp("apartment", seed=3)
    sim.set_no_go_zones([BATHROOM])
    assert sim.goto(2.8, 2.2, label="living room") is True
    assert sim.mode is FlightMode.UNDOCKING  # departing the dock to fly


def test_patrol_drops_zone_waypoints_and_flies_the_rest() -> None:
    sim = SimulatedBlimp("apartment", seed=3)
    sim.set_no_go_zones([BATHROOM])
    sim.patrol([
        ("living room", "area", 2.8, 2.2),
        ("bathroom sink", "area", 8.0, 1.5),
    ])
    assert sim.mode is FlightMode.UNDOCKING
    assert [w[0] for w in sim._route] == ["living room"]
    emissions = sim.tick(0.02)
    assert any(t == topics.FLIGHT_REFUSED for t, _ in emissions)


def test_dispatch_with_all_waypoints_in_zones_stays_docked() -> None:
    sim = SimulatedBlimp("apartment", seed=3)
    # Ruth's chair (the only person waypoint) sits at (6.6, 4.6) in the bedroom
    sim.set_no_go_zones([Zone("the bedroom", 4.5, 3.0, 4.5, 3.5)])
    sim.dispatch("checkin")
    assert sim.mode is FlightMode.DOCKED
    emissions = sim.tick(0.02)
    refused = [p for t, p in emissions if t == topics.FLIGHT_REFUSED]
    assert refused and refused[0]["label"] == "Ruth's chair"
