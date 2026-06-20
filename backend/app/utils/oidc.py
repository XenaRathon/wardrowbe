import logging
import os
import time
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from app.config import get_settings

logger = logging.getLogger(__name__)

_jwk_clients: dict[str, PyJWKClient] = {}
_jwks_cache_times: dict[str, float] = {}
JWKS_CACHE_TTL = 3600


def _get_jwk_client(jwks_uri: str) -> PyJWKClient:
    now = time.time()
    cached_time = _jwks_cache_times.get(jwks_uri, 0)
    if jwks_uri in _jwk_clients and (now - cached_time) < JWKS_CACHE_TTL:
        return _jwk_clients[jwks_uri]

    client = PyJWKClient(jwks_uri)
    _jwk_clients[jwks_uri] = client
    _jwks_cache_times[jwks_uri] = now
    return client


async def validate_oidc_id_token(
    id_token: str,
    issuer_url: str,
    client_id: str | list[str],
) -> dict:
    settings = get_settings()

    # OIDC_DISCOVERY_BASE_URL lets us fetch discovery + JWKS over a local
    # network path that bypasses Cloudflare (which 403s non-browser UAs on
    # the public JWKS endpoint). The issuer_url is still the public URL for
    # iss-claim validation, because that's what Authentik stamps on tokens.
    discovery_base = os.environ.get("OIDC_DISCOVERY_BASE_URL") or issuer_url

    try:
        discovery_url = f"{discovery_base.rstrip('/')}/.well-known/openid-configuration"
        async with httpx.AsyncClient(
            timeout=10, verify=not settings.debug, follow_redirects=True
        ) as client:
            disc_resp = await client.get(discovery_url)
            disc_resp.raise_for_status()
            discovery = disc_resp.json()
            jwks_uri = discovery["jwks_uri"]
            # Validate the token's iss claim against the provider's canonical issuer
            # (the discovery metadata) rather than the configured env var, so a
            # trailing slash on OIDC_ISSUER_URL cannot cause a false issuer mismatch.
            expected_issuer = discovery.get("issuer", issuer_url.rstrip("/"))
    except httpx.HTTPError as e:
        logger.error("Failed to fetch OIDC discovery from %s: %s", discovery_base, e)
        raise ValueError("Failed to contact OIDC provider") from None

    audience = [client_id] if isinstance(client_id, str) else client_id

    try:
        jwk_client = _get_jwk_client(jwks_uri)
        signing_key = jwk_client.get_signing_key_from_jwt(id_token)
        try:
            unverified_header = jwt.get_unverified_header(id_token)
            unverified_payload = jwt.decode(id_token, options={"verify_signature": False})
            logger.error(
                "[OIDC DEBUG] header=%s expected_issuer=%r expected_audience=%r token_iss=%r token_aud=%r token_sub=%r token_exp=%r",
                unverified_header,
                issuer_url,
                audience,
                unverified_payload.get("iss"),
                unverified_payload.get("aud"),
                unverified_payload.get("sub"),
                unverified_payload.get("exp"),
            )
        except Exception as _debug_e:
            logger.error("[OIDC DEBUG] failed to dump unverified token: %s", _debug_e)
        payload: dict[str, Any] = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=audience,
            issuer=expected_issuer,
            options={"verify_exp": True},
        )
    except jwt.PyJWTError as e:
        logger.error("[OIDC DEBUG] PyJWT validation failed: %s: %s", type(e).__name__, e)
        raise ValueError(f"Invalid OIDC token: {type(e).__name__}: {e}") from None

    return payload
