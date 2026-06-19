"""The public /reference/exercises endpoint — contract for the reference view.

Asserts the bundle the frontend relies on: two Watt exercises, each with a
laid-out PenFile (so the diagram renders), the textbook's independent answer key,
verification verdicts, and a clean structural check.
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def _fetch() -> list[dict]:
    from main import app

    resp = TestClient(app).get("/reference/exercises")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _by_key(data: list[dict], key: str) -> dict:
    return next(e for e in data if e["key"] == key)


def test_returns_both_watt_exercises() -> None:
    data = _fetch()
    keys = {e["key"] for e in data}
    assert keys == {"watt_b_ex1_manufacturer", "watt_b_ex2_car_dealership"}


def test_manufacturer_pen_has_junctions_and_layout() -> None:
    ex = _by_key(_fetch(), "watt_b_ex1_manufacturer")
    names = {e["name"] for e in ex["pen"]["erd"]["entities"]}
    assert {"comp_supp", "build"} <= names  # M:N resolved by junction entities
    assert ex["pen"]["layout"]["erd"]["nodes"], "diagram must come pre-laid-out"
    assert any("CompSupp" in line for line in ex["reference_answer_key"])
    assert ex["violations"] == []  # clean answer key


def test_car_dealership_sales_rule_is_enforced() -> None:
    ex = _by_key(_fetch(), "watt_b_ex2_car_dealership")
    sells = next(r for r in ex["rules"]
                 if r["statement"].startswith("A salesperson may sell many cars"))
    assert sells["status"] == "enforced"
    assert ex["violations"] == []
    assert ex["reference_answer_key"]
    assert ex["source"].startswith("Watt")
