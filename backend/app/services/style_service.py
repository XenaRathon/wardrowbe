"""Style-profile assembly + AI draft (advisory colour-season/Kibbe lean).

Combines the deterministic body-shape analysis (Task 2's `body_analysis.py`)
with the confirmed fields a user has saved on their `UserPreference.style_profile`,
and offers an AI-assisted "draft" of colour-season + Kibbe lean that the user
can review/confirm before it's persisted via the PUT endpoint.
"""

import json
import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.user import User
from app.schemas.preference import StyleProfile
from app.services.ai_service import AIDisabledError, get_ai_service, require_internal_ai
from app.services.body_analysis import analyze_measurements
from app.services.preference_service import PreferenceService
from app.style_rules import SEASON_PALETTE

logger = logging.getLogger(__name__)

# Kibbe body-type "leans" (simplified to the five family archetypes; see
# schemas/preference.py's StyleProfile.kibbe_lean comment for the canonical set).
KNOWN_KIBBE_LEANS = {"dramatic", "natural", "romantic", "classic", "gamine"}

DRAFT_SYSTEM_PROMPT = (
    "You are a styling assistant. Given measurements-derived shape context plus "
    "user-provided hints and an optional photo, propose the most likely 12-season "
    "colour-season and Kibbe body-type lean. Be decisive but only use the provided "
    "context. "
    'OUTPUT ONLY JSON: {"color_season": "<one of the 12-season names>", '
    '"kibbe_lean": "<dramatic|natural|romantic|classic|gamine>"}'
)


class StyleDraftError(Exception):
    """Raised when the AI draft call ultimately fails (all endpoints unreachable/erroring)."""


class StyleService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.preference_service = PreferenceService(db)

    async def get_profile(self, user: User) -> dict:
        """Assemble the full style profile: deterministic body analysis + confirmed AI fields."""
        analysis = analyze_measurements(user.body_measurements or {})
        preferences = await self.preference_service.get_or_create_preferences(user.id)
        profile = StyleProfile(**(preferences.style_profile or {}))

        return {
            "measurements": user.body_measurements or {},
            "body_shape": analysis["body_shape"],
            "vertical_line": analysis["vertical_line"],
            "frame": analysis["frame"],
            "color_season": profile.color_season,
            "kibbe_lean": profile.kibbe_lean,
            "palette": profile.palette,
            "season_confirmed": profile.season_confirmed,
            "kibbe_confirmed": profile.kibbe_confirmed,
        }

    async def update_confirmed(self, user: User, fields: dict) -> None:
        """Persist user-confirmed style-profile fields (color_season, kibbe_lean, etc.)."""
        preferences = await self.preference_service.get_or_create_preferences(user.id)

        profile = StyleProfile(**(preferences.style_profile or {}))
        for field in ("color_season", "kibbe_lean", "palette", "season_confirmed", "kibbe_confirmed"):
            if field in fields:
                setattr(profile, field, fields[field])

        preferences.style_profile = profile.model_dump()
        flag_modified(preferences, "style_profile")
        await self.db.commit()

    async def draft(
        self, user: User, hints: dict | None = None, image_b64: str | None = None
    ) -> dict:
        """Ask the local model for an advisory (unsaved) colour-season + Kibbe lean guess."""
        # Guard first so deferral is unconditional, before any context assembly. An
        # image-bearing draft needs vision specifically; a text-only draft only needs text.
        require_internal_ai("vision" if image_b64 else "text")

        analysis = analyze_measurements(user.body_measurements or {})
        context_lines = [f"{key}: {value}" for key, value in analysis.items() if value]
        for key, value in (hints or {}).items():
            if value:
                context_lines.append(f"{key}: {value}")
        user_text = "\n".join(context_lines) or "No additional context provided."

        try:
            raw = await self._call_model(user_text, image_b64)
        except (StyleDraftError, AIDisabledError):
            raise
        except Exception as e:
            logger.error(f"AI style-draft failed: {e}")
            raise StyleDraftError(
                "AI service is not available. Please check your AI endpoint configuration in Settings."
            ) from e

        color_season = raw.get("color_season") if raw else None
        kibbe_lean = raw.get("kibbe_lean") if raw else None

        if not isinstance(color_season, str) or color_season not in SEASON_PALETTE:
            color_season = None
        if not isinstance(kibbe_lean, str) or kibbe_lean not in KNOWN_KIBBE_LEANS:
            kibbe_lean = None

        return {"color_season": color_season, "kibbe_lean": kibbe_lean}

    async def _call_model(self, user_text: str, image_b64: str | None) -> dict:
        """Single AI entry point for `draft` -- isolated so tests can patch it directly."""
        ai_service = get_ai_service()

        content: Any
        if image_b64:
            content = [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                },
            ]
        else:
            content = user_text

        messages = [
            {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]

        response_text, err, _ = await ai_service._call_with_fallback(
            messages, "style-draft", use_vision_model=bool(image_b64)
        )
        if not response_text:
            if err:
                raise err
            return {}
        return self._extract_json(response_text)

    @staticmethod
    def _extract_json(text: str) -> dict:
        try:
            data = json.loads(text.strip())
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                pass

        logger.warning(f"Could not parse JSON from style-draft response: {text[:200]}")
        return {}
