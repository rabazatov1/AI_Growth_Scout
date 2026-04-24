import json
from datetime import datetime
from pathlib import Path

from src.config import settings
from src.models import ScoredOpportunity


def export_results_to_json(
    results: list[ScoredOpportunity],
    path: Path | None = None,
) -> tuple[Path, str]:
    settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = path or settings.CACHE_DIR / f"results_{ts}.json"

    call_repr = f"export_results_to_json(count={len(results)}, path={str(target)!r})"

    payload = []
    for sr in results:
        payload.append({
            "score": sr.score,
            "reason": sr.reason,
            **sr.opportunity.model_dump(),
        })

    with open(target, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return target, call_repr
