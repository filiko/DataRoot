"""Schema 0.2 additions are optional-with-defaults: schemaVersion 0.1 project
JSON (no indexes/enum_values/description/color) must validate unchanged.
REQ-DATA-071."""
import json
from pathlib import Path

import pytest

from models.pen import Attribute, Entity, IndexDef, PenFile

DEMO_ASSETS = Path(__file__).resolve().parents[1] / "demo_assets"


@pytest.mark.parametrize("asset", sorted(DEMO_ASSETS.glob("*.dfd.json")), ids=lambda p: p.name)
def test_bundled_0_1_assets_still_validate(asset: Path):
    pen = PenFile.model_validate(json.loads(asset.read_text(encoding="utf-8")))
    for entity in pen.erd.entities:
        assert entity.indexes == []
        assert entity.description is None
        assert entity.color is None
        for attr in entity.attributes:
            assert attr.enum_values is None


def test_minimal_0_1_json_validates():
    pen = PenFile.model_validate({
        "documentType": "dashbot.dfdmaker",
        "schemaVersion": "0.1",
        "erd": {
            "entities": [{
                "name": "orders",
                "display_name": "Orders",
                "attributes": [{"name": "id", "pg_type": "uuid", "key_role": "primary"}],
            }],
        },
    })
    assert pen.schemaVersion == "0.1"  # explicit value preserved, not coerced
    assert pen.erd.entities[0].indexes == []


def test_0_2_fields_round_trip():
    entity = Entity(
        name="orders",
        display_name="Orders",
        description="Customer orders",
        color="#fde68a",
        attributes=[Attribute(name="status", pg_type="text", enum_values=["open", "closed"])],
        indexes=[IndexDef(name="idx_orders_status", attribute_ids=["a1"], unique=True)],
    )
    pen = PenFile()
    pen.erd.entities.append(entity)
    reloaded = PenFile.model_validate(json.loads(pen.model_dump_json(by_alias=True)))
    ent = reloaded.erd.entities[0]
    assert ent.description == "Customer orders"
    assert ent.color == "#fde68a"
    assert ent.indexes[0].unique is True
    assert ent.attributes[0].enum_values == ["open", "closed"]
    assert reloaded.schemaVersion == "0.2"
