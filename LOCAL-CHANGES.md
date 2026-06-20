# Local fork changes — keep vs drop when syncing upstream

This fork tracks upstream [`Anyesh/wardrowbe`](https://github.com/Anyesh/wardrowbe) and pulls
upstream changes **automatically** (a daily `sync-upstream.sh` that merges clean updates and
flags conflicts). The goal is to stay current and **only fill gaps**, not maintain a divergent
fork. When an upstream change *conflicts* with a local change, resolve like this:

## KEEP — environment-specific fixes (upstream will never provide these)
- **Native Ollama `/api/chat` with `think: false`** — `backend/app/services/ai_service.py`.
  qwen3.5 is a reasoning model; on the OpenAI `/v1` endpoint it loops in `<think>` and returns
  empty tags/descriptions. This is specific to the local model/host, not a gap upstream fills.
- **`max_jobs = 1`** — `backend/app/workers/worker.py`. Serial processing so the single-GPU
  Ollama doesn't wedge under concurrent vision calls. Tune to your hardware; don't drop.

## DROP — gap-fills, once upstream provides an equivalent (prefer upstream)
- Expanded clothing categories (intimates / activewear / jewelry, watch, sunglasses, gloves)
- Auto background-removal before AI tagging (`auto_remove_background`, in the tagging worker)
- Outfit completeness enforcement (top+bottom or one-piece + shoes; accessories never core)

If upstream implements any of the "drop" items, remove the local version and take upstream's.

*Maintained with help of Claude (Anthropic).*
