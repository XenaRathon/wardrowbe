import pytest

from app.services.ai_service import VALID_TYPES
from app.taxonomy import CATEGORY_TYPES, SUBTYPES, category_for_type


def test_every_valid_type_has_exactly_one_category():
    assigned = [t for types in CATEGORY_TYPES.values() for t in types]
    # no type appears in two categories
    assert len(assigned) == len(set(assigned))
    # every VALID_TYPES member is categorized
    missing = VALID_TYPES - set(assigned)
    assert not missing, f"uncategorized types: {sorted(missing)}"


def test_category_for_type_reverse_lookup():
    assert category_for_type("bra") == "Intimates"
    assert category_for_type("jeans") == "Bottoms"
    assert category_for_type("unknown") is None
    assert category_for_type("not-a-type") is None


def test_subtypes_only_reference_known_types():
    assert set(SUBTYPES).issubset(VALID_TYPES)
    assert "push-up" in SUBTYPES["bra"]
    assert "crop" in SUBTYPES["top"]


@pytest.mark.asyncio
async def test_taxonomy_endpoint(client, auth_headers):
    r = await client.get("/api/v1/taxonomy", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    cats = {c["category"] for c in data["categories"]}
    assert "Intimates" in cats and "Tops" in cats
    intimates = next(c for c in data["categories"] if c["category"] == "Intimates")
    bra = next(t for t in intimates["types"] if t["type"] == "bra")
    assert "push-up" in bra["subtypes"]
