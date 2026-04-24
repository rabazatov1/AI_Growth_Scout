import json
from pathlib import Path

from src.config import settings
from src.models import Opportunity


def load_curated_opportunities(
    path: Path | None = None,
) -> tuple[list[Opportunity], str]:
    target = path or settings.CURATED_PATH
    call_repr = f"load_curated_opportunities(path={str(target)!r})"

    if not target.exists():
        return [], call_repr

    with open(target, encoding="utf-8") as f:
        raw = json.load(f)

    opportunities = []
    for item in raw:
        try:
            opportunities.append(Opportunity(**item))
        except Exception:
            continue

    return opportunities, call_repr
