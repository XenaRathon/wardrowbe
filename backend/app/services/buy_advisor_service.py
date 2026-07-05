"""Buy-Advisor: closet-gap recommendations with prefilled search links, plus a
paste-a-product-URL "what size do I buy" helper (chart parse via LLM, with a
measurement-based fallback that never fails the request).
"""

import json
import logging
import re
import urllib.parse

import httpx
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import ClothingItem, ItemStatus
from app.models.user import User
from app.services.ai_service import AIDisabledError, get_ai_service, require_internal_ai
from app.services.gap_analysis import analyze_gaps
from app.services.sizing import bra_size, generic_size
from app.services.style_service import StyleService
from app.style_rules import flattering_attrs, palette_for
from app.utils.clothing import INTIMATE_TYPES

logger = logging.getLogger(__name__)

# role (from analyze_gaps) -> a representative garment type to search/size for
_ROLE_TO_TYPE = {
    "bottom": "jeans",
    "base_top": "top",
    "footwear": "sneakers",
    "outer_layer": "blazer",
}

_TOP_N_GAPS = 3
_MAX_CHART_CHARS = 8000

_CHART_SYSTEM_PROMPT = (
    "Extract the size chart as JSON {size:{chest,waist,hips}} from this page text. "
    "OUTPUT ONLY JSON."
)


class BuyAdvisorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _owned_types(self, user: User) -> list[str]:
        """The user's own ready, non-archived item types (per-user, not the shared pool)."""
        result = await self.db.execute(
            select(ClothingItem.type).where(
                and_(
                    ClothingItem.user_id == user.id,
                    ClothingItem.status == ItemStatus.ready,
                    ClothingItem.is_archived.is_(False),
                )
            )
        )
        return [row[0] for row in result.all()]

    async def recommendations(self, user: User) -> list[dict]:
        types = await self._owned_types(user)
        gaps = analyze_gaps(types)

        profile = await StyleService(self.db).get_profile(user)
        body_shape = profile.get("body_shape") if profile else None
        color_season = profile.get("color_season") if profile else None

        silhouettes = flattering_attrs(body_shape).get("recommended", {}).get("silhouette")
        silhouette = sorted(silhouettes)[0] if silhouettes else None
        palette = palette_for(color_season)
        color = palette[0] if palette else None

        recs = []
        for gap in gaps[:_TOP_N_GAPS]:
            role = gap["role"]
            garment_type = _ROLE_TO_TYPE.get(role, "top")

            rationale = gap.get("reason", "")
            if silhouette or color:
                extras = []
                if silhouette:
                    extras.append(f"a {silhouette} silhouette")
                if color:
                    extras.append(f"a {color} colourway")
                rationale = f"{rationale} Look for {' and '.join(extras)} to match your style profile."

            query_parts = [p for p in (color, silhouette, garment_type) if p]
            query = " ".join(query_parts)

            recs.append(
                {
                    "role": role,
                    "type": garment_type,
                    "silhouette": silhouette,
                    "color": color,
                    "rationale": rationale,
                    "search_links": self._search_links(query),
                }
            )
        return recs

    def _search_links(self, query: str) -> list[dict]:
        """Prefilled search URLs -- no scraping, just deep-links a user can click."""
        encoded = urllib.parse.quote(query)
        return [
            {"retailer": "Google Shopping", "url": f"https://www.google.com/search?tbm=shop&q={encoded}"},
            {"retailer": "Amazon", "url": f"https://www.amazon.com/s?k={encoded}"},
        ]

    async def size_for_url(self, user: User, product_url: str, product_type: str | None = None) -> dict:
        measurements = user.body_measurements or {}

        if (product_type or "").lower() in INTIMATE_TYPES:
            underbust = measurements.get("underbust")
            bust = measurements.get("bust")
            try:
                result = bra_size(underbust, bust)
            except Exception as e:
                logger.warning(f"size_for_url bra_size failed, falling back to measurements: {e}")
                result = None
            if result:
                return {"size": result["label"], "confidence": "high", "source": "bra-baseline"}
            # Missing/invalid underbust or bust (e.g. non-numeric strings) --
            # fall through to the measurement-based fallback below rather
            # than returning a None-based result or raising.

        try:
            page = await self._fetch_page(product_url)
            chart = await self._parse_chart(page) if page else None
            if chart:
                size = self._match_chart_size(chart, measurements)
                if size:
                    return {"size": size, "confidence": "medium", "source": "chart"}
        except Exception as e:
            logger.warning(f"size_for_url chart lookup failed, falling back to measurements: {e}")

        return {
            "size": generic_size(measurements),
            "confidence": "low",
            "source": "measurement",
        }

    @staticmethod
    def _match_chart_size(chart: dict, measurements: dict) -> str | None:
        """Pick the chart size whose chest/bust is the smallest value >= the user's
        chest; if none qualify, fall back to the nearest value overall."""
        user_chest = measurements.get("chest")
        if user_chest is None:
            user_chest = measurements.get("bust")
        if user_chest is None:
            return None
        try:
            user_chest = float(user_chest)
        except (TypeError, ValueError):
            return None

        candidates = []
        for size, attrs in (chart or {}).items():
            if not isinstance(attrs, dict):
                continue
            value = attrs.get("chest")
            if value is None:
                value = attrs.get("bust")
            if value is None:
                continue
            try:
                candidates.append((size, float(value)))
            except (TypeError, ValueError):
                continue

        if not candidates:
            return None

        at_or_above = [c for c in candidates if c[1] >= user_chest]
        if at_or_above:
            return min(at_or_above, key=lambda c: c[1])[0]

        return min(candidates, key=lambda c: abs(c[1] - user_chest))[0]

    async def _fetch_page(self, url: str) -> str | None:
        try:
            async with httpx.AsyncClient(
                timeout=10,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; WardrowbeBuyAdvisor/1.0)"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except httpx.HTTPError as e:
            logger.warning(f"Buy-advisor page fetch failed for {url}: {e}")
            return None

    async def _parse_chart(self, page_text: str) -> dict | None:
        require_internal_ai("text")
        try:
            ai_service = get_ai_service()
            truncated = (page_text or "")[:_MAX_CHART_CHARS]
            raw = await ai_service.generate_text(truncated, system_prompt=_CHART_SYSTEM_PROMPT)
            return self._extract_json(raw)
        except AIDisabledError:
            raise
        except Exception as e:
            logger.warning(f"Buy-advisor chart parse failed: {e}")
            return None

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        if not text:
            return None
        try:
            data = json.loads(text.strip())
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                pass

        return None
