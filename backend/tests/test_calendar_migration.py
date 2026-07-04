import pytest
from sqlalchemy import inspect, text


@pytest.mark.asyncio
async def test_new_columns_exist(db_session):
    rows = (await db_session.execute(text(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE (table_name='clothing_items' AND column_name='is_private') "
        "OR (table_name='item_history' AND column_name='worn_by_user_id') "
        "OR (table_name='outfits' AND column_name='worn_at') "
        "OR (table_name='user_preferences' AND column_name IN ('wear_nudge_enabled','wear_nudge_time'))"
    ))).all()
    found = {(t, c) for t, c in rows}
    assert ("clothing_items", "is_private") in found
    assert ("item_history", "worn_by_user_id") in found
    assert ("outfits", "worn_at") in found
    assert ("user_preferences", "wear_nudge_enabled") in found
    assert ("user_preferences", "wear_nudge_time") in found
