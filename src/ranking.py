import re

from src.models import Opportunity, QueryIntent, ScoreBreakdown, ScoredOpportunity
from src.utils import days_until, deduplicate, normalize_text

_DEFAULT_THRESHOLD = 5.0
_RELAXED_THRESHOLD = 3.5
_MIN_RESULTS_BEFORE_RELAX = 1

_CLOSE_TYPES: dict[str, set[str]] = {
    "internship": {"traineeship"},
    "traineeship": {"internship"},
    "hackathon": {"competition"},
    "competition": {"hackathon"},
    "program": {"bootcamp", "course"},
    "course": {"program", "bootcamp"},
}

_LEVEL_TABLE: dict[str, dict[str, float]] = {
    "beginner": {"beginner": 15.0, "intermediate": 8.0, "advanced": 2.0},
    "intermediate": {"beginner": 7.0, "intermediate": 15.0, "advanced": 8.0},
    "advanced": {"beginner": 4.0, "intermediate": 10.0, "advanced": 15.0},
}


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _norm(text: str) -> str:
    normalized = normalize_text(str(text))
    return re.sub(r"\s+", " ", normalized).strip()


def _title_key(opp: Opportunity) -> str:
    return _norm(opp.title)[:60] + "|" + _norm(opp.source_name)


def _calculate_relevance_score(opp: Opportunity, intent: QueryIntent) -> float:
    title_n = _norm(opp.title)
    desc_n = _norm(opp.description or "")
    tags_n = [_norm(t) for t in opp.topic_tags]
    skills_n = [_norm(s) for s in opp.skills]

    raw = 0.0
    for kw in intent.keywords:
        kw_n = _norm(kw)
        if kw_n in title_n:
            raw += 12
        elif kw_n in desc_n:
            raw += 5
        if any(kw_n in tag for tag in tags_n):
            raw += 8
        if any(kw_n in skill for skill in skills_n):
            raw += 6

    if intent.topics:
        tags_set = {_norm(t) for t in opp.topic_tags}
        for topic in intent.topics:
            if _norm(topic) in tags_set:
                raw += 7

    return raw


def _calculate_type_score(opp: Opportunity, intent: QueryIntent) -> float:
    if not intent.type_preferences:
        return 8.0
    for pref in intent.type_preferences:
        if pref == opp.type:
            return 20.0
        if opp.type in _CLOSE_TYPES.get(pref, set()):
            return 10.0
    return 0.0


def _calculate_level_score(opp: Opportunity, intent: QueryIntent) -> float:
    user_level = intent.user_level
    if user_level is None and intent.is_beginner:
        user_level = "beginner"
    if user_level is None:
        return 6.0
    return _LEVEL_TABLE.get(user_level, {}).get(opp.level, 6.0)


def _calculate_remote_score(opp: Opportunity, intent: QueryIntent) -> float:
    if not intent.wants_remote:
        return 5.0
    return 10.0 if opp.remote else 0.0


def _calculate_deadline_score(opp: Opportunity, urgent: bool = False) -> float:
    days = days_until(opp.deadline)
    if days is None:
        return 10.0 if urgent else 3.0
    if days < 0:
        return 0.0
    if urgent:
        if days <= 7:  return 35.0
        if days <= 30: return 25.0
        if days <= 90: return 15.0
        return 5.0
    else:
        if days <= 7:  return 10.0
        if days <= 30: return 7.0
        if days <= 90: return 4.0
        return 2.0


def _calculate_penalties(opp: Opportunity) -> float:
    p = 0.0

    days = days_until(opp.deadline)
    if days is not None and days < 0:
        p -= 100.0

    if not opp.description or len(opp.description.strip()) < 30:
        p -= 5.0

    if not opp.skills and not opp.topic_tags:
        p -= 5.0

    if not opp.title or len(opp.title.strip()) < 2:
        p -= 10.0

    has_desc = bool(opp.description and len(opp.description.strip()) >= 30)
    has_meta = bool(opp.skills or opp.topic_tags)
    has_url = bool(opp.source_url)
    if not has_desc and not has_meta and not has_url:
        p -= 10.0

    return p


_TYPE_LABELS: dict[str, str] = {
    "internship": "стажировка",
    "hackathon": "хакатон",
    "program": "образовательная программа",
    "course": "курс",
}


def _build_reason(opp: Opportunity, intent: QueryIntent, breakdown: ScoreBreakdown) -> str:
    parts: list[str] = []

    title_n = _norm(opp.title)
    desc_n = _norm(opp.description or "")
    matched = [kw for kw in intent.keywords if _norm(kw) in title_n or _norm(kw) in desc_n]
    if matched:
        parts.append(f"совпадение: {', '.join(dict.fromkeys(matched))}")

    if intent.topics:
        tags_set = {_norm(t) for t in opp.topic_tags}
        overlap = [t for t in intent.topics if _norm(t) in tags_set]
        if overlap:
            parts.append(f"темы: {', '.join(overlap)}")

    if breakdown.type_score >= 20.0:
        parts.append(_TYPE_LABELS.get(opp.type, opp.type))

    if breakdown.level_score >= 14.5:
        parts.append("уровень совпал")

    if intent.wants_remote and opp.remote:
        parts.append("удалённо")

    days = days_until(opp.deadline)
    if days is not None and 0 <= days <= 7:
        parts.append(f"дедлайн через {days}д!")
    elif days is not None and 0 <= days <= 30:
        parts.append(f"дедлайн через {days}д")

    if not parts and opp.topic_tags:
        parts.append(f"охватывает: {', '.join(opp.topic_tags[:3])}")

    return "; ".join(parts) if parts else "подходит по контексту"


def _calculate_opportunity_score(
        opp: Opportunity,
        intent: QueryIntent,
) -> tuple[float, float, str, ScoreBreakdown]:
    urgent = intent.is_urgent

    rel_raw = _calculate_relevance_score(opp, intent)
    typ_raw = _calculate_type_score(opp, intent)
    lvl_raw = _calculate_level_score(opp, intent)
    rem_raw = _calculate_remote_score(opp, intent)
    dl_raw = _calculate_deadline_score(opp, urgent=urgent)
    pen = _calculate_penalties(opp)

    if urgent:
        rel = min(35.0, rel_raw)
        typ = min(15.0, typ_raw)
        lvl = min(10.0, lvl_raw)
        rem = min(5.0, rem_raw)
        dl = min(35.0, dl_raw)
    else:
        rel = min(45.0, rel_raw)
        typ = min(20.0, typ_raw)
        lvl = min(15.0, lvl_raw)
        rem = min(10.0, rem_raw)
        dl = min(10.0, dl_raw)

    breakdown = ScoreBreakdown(
        relevance_score=round(rel, 2),
        type_score=round(typ, 2),
        level_score=round(lvl, 2),
        remote_score=round(rem, 2),
        deadline_score=round(dl, 2),
        penalties=round(pen, 2),
    )

    score_100 = _clamp(rel + typ + lvl + rem + dl + pen)
    score_10 = round(score_100 / 10, 1)
    reason = _build_reason(opp, intent, breakdown)

    return score_10, score_100, reason, breakdown


def filter_and_rank_opportunities(
        opportunities: list[Opportunity],
        intent: QueryIntent,
        top_k: int = 5,
) -> tuple[list[ScoredOpportunity], str]:
    call_repr = (
        f"filter_and_rank_opportunities("
        f"count={len(opportunities)}, "
        f"beginner={intent.is_beginner}, "
        f"topics={intent.topics}, "
        f"top_k={top_k})"
    )

    unique = deduplicate(opportunities, _title_key)

    scored: list[ScoredOpportunity] = []
    for opp in unique:
        score_10, score_100, reason, breakdown = _calculate_opportunity_score(opp, intent)
        scored.append(ScoredOpportunity(
            opportunity=opp,
            score=score_10,
            score_100=score_100,
            reason=reason,
            breakdown=breakdown,
        ))

    def _sort_key(x: ScoredOpportunity) -> tuple[float, int]:
        days = days_until(x.opportunity.deadline)
        dl_sort = days if (days is not None and days >= 0) else 9999
        return (-x.score, dl_sort)

    scored.sort(key=_sort_key)

    above = [s for s in scored if s.score >= _DEFAULT_THRESHOLD]
    if len(above) < _MIN_RESULTS_BEFORE_RELAX:
        above = [s for s in scored if s.score >= _RELAXED_THRESHOLD]

    return above[:top_k], call_repr
