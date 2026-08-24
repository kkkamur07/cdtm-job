"""The career flow, the people in one box of it, and one member's path."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.integration.conftest import _engine, insert_member

pytestmark = pytest.mark.integration
API = "/api/v1/paths"


def test_paths_flow_and_member_path(client: TestClient, member_anna: dict) -> None:
    insert_member("carl-test", "Carl Test")
    with _engine.begin() as conn:
        conn.execute(
            text(
                "insert into member_paths (member_id, study_group, first_step_group, current_group) "
                "select id, 'Business & Management', 'Consulting', 'Founder' from members where slug = 'anna-test'"
            )
        )
        conn.execute(
            text(
                "insert into member_paths (member_id, study_group, first_step_group, current_group) "
                "select id, 'Computer Science', 'Big Tech', 'Founder' from members where slug = 'carl-test'"
            )
        )
    h = member_anna["headers"]
    r = client.get(f"{API}/flow", headers=h)
    assert r.status_code == 200, r.text
    flow = r.json()
    assert flow["members_counted"] == 2
    assert {"stage": "current", "group": "Founder", "count": 2} in flow["nodes"]
    assert any(
        l["source_group"] == "Consulting" and l["target_group"] == "Founder" for l in flow["links"]
    )
    r = client.get(f"{API}/members", params={"stage": "current", "group": "Founder"}, headers=h)
    assert r.json()["total"] == 2
    r = client.get(f"{API}/members/anna-test", headers=h)
    assert r.json()["first_step_group"] == "Consulting"
    assert client.get(f"{API}/groups", headers=h).json()["current"] == ["Founder"]


def test_the_flow_has_an_intent_column(client: TestClient, member_anna: dict) -> None:
    """The fourth stage is what people say they are open to, not another career step."""
    h = member_anna["headers"]
    with _engine.begin() as conn:
        conn.execute(
            text(
                "insert into member_paths (member_id, study_group, current_group) "
                "select id, 'Computer Science', 'Founder' from members where slug = 'anna-test'"
            )
        )
    client.put("/api/v1/members/me/intents", json={"mentoring": True, "investing": True}, headers=h)
    flow = client.get(f"{API}/flow", headers=h).json()
    assert {"stage": "intent", "group": "Mentoring", "count": 1} in flow["nodes"]
    assert {"stage": "intent", "group": "Investing", "count": 1} in flow["nodes"]
    # One member with two intents is two links out of their current box, not one.
    out = [
        link
        for link in flow["links"]
        if link["source_stage"] == "current" and link["target_stage"] == "intent"
    ]
    assert {link["target_group"] for link in out} == {"Mentoring", "Investing"}
    assert client.get(f"{API}/groups", headers=h).json()["intent"][0] == "Co-founding"


def test_a_member_with_no_intents_lands_in_not_stated(
    client: TestClient, member_anna: dict
) -> None:
    h = member_anna["headers"]
    with _engine.begin() as conn:
        conn.execute(
            text(
                "insert into member_paths (member_id, current_group) "
                "select id, 'Consulting' from members where slug = 'anna-test'"
            )
        )
    flow = client.get(f"{API}/flow", headers=h).json()
    assert {"stage": "intent", "group": "Not stated", "count": 1} in flow["nodes"]
