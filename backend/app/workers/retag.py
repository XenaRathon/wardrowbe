"""Nightly re-tag backfill worker.

Items tagged before the cut-attribute feature (neckline/rise/silhouette/
sleeve_length) shipped have never been checked for those attributes. This
worker re-runs AI tagging on a bounded, serial batch of such items each night
so they pick up the new attributes without a manual re-tag.

Candidates are selected via `cut_attrs_checked_at IS NULL`, not "all four cut
attrs are NULL" — many item types (footwear, bags, belts, socks, ties,
jewelry, watches, hats, gloves, scarves, ...) legitimately never get cut
attributes, so `analyze_image` returns all-None for them and the old
all-NULL gate re-selected them forever (a real GPU call every night,
starving genuinely-enrichable items out of the bounded batch). Setting
`cut_attrs_checked_at` after a successful analysis — regardless of whether it
produced any cut attribute — gives every item a terminal "checked" state.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import and_, select

from app.config import get_settings
from app.models.item import ClothingItem, ItemStatus
from app.services.ai_service import AIService
from app.workers.db import get_db_session
from app.workers.tagging import tags_to_item_fields

logger = logging.getLogger(__name__)

# Keep the batch small: tagging is serial (single-GPU Ollama, worker max_jobs=1),
# so a large batch would block the queue for the whole cron run. Ordering by
# updated_at means the next nightly run naturally resumes where this one left off,
# because items just re-tagged get a fresh updated_at and sort to the back.
BATCH_SIZE = 20

# The four cut attributes introduced by the Styler tagging feature.
CUT_ATTRIBUTES = ("neckline", "rise", "silhouette", "sleeve_length")


async def check_retag_backfill(ctx: dict):
    """Backfill cut attributes for a bounded batch of pre-feature items.

    arq's cron scheduling gives each scheduled run a single, deterministic
    job id cluster-wide, so this doesn't double up even if multiple worker
    processes share the same redis queue — no separate distributed lock is
    needed on top of that (matches `recover_stale_processing_items` /
    `update_learning_profiles`, the other unlocked crons in this worker).
    """
    logger.info("Checking for items needing cut-attribute re-tag backfill...")

    db = get_db_session(ctx)
    try:
        result = await db.execute(
            select(ClothingItem)
            .where(
                and_(
                    ClothingItem.status == ItemStatus.ready,
                    ClothingItem.image_path.isnot(None),
                    ClothingItem.cut_attrs_checked_at.is_(None),
                )
            )
            .order_by(ClothingItem.updated_at)
            .limit(BATCH_SIZE)
        )
        items = list(result.scalars().all())

        if not items:
            logger.info("No items need cut-attribute backfill")
            return {"retagged": 0}

        ai_service = AIService()
        retagged = 0
        storage_path = get_settings().storage_path

        for item in items:
            try:
                full_path = f"{storage_path}/{item.image_path}"
                tags = await ai_service.analyze_image(full_path)
                fields = tags_to_item_fields(tags)

                for field in CUT_ATTRIBUTES:
                    setattr(item, field, fields[field])
                if item.subtype is None:
                    item.subtype = fields["subtype"]
                # Mark checked regardless of whether any cut attribute came
                # back non-None — un-enrichable types (footwear, bags, etc.)
                # must still leave the candidate set permanently.
                item.cut_attrs_checked_at = datetime.now(UTC)

                await db.commit()
                retagged += 1
                logger.info(f"Backfilled cut attributes for item {item.id}")
            except Exception as e:
                logger.warning(f"Failed to backfill cut attributes for item {item.id}: {e}")
                await db.rollback()
                continue

        logger.info(f"Backfilled cut attributes for {retagged}/{len(items)} items")
        return {"retagged": retagged, "checked": len(items)}

    except Exception as e:
        logger.exception("Error in check_retag_backfill")
        return {"retagged": 0, "error": str(e)}
    finally:
        await db.close()
