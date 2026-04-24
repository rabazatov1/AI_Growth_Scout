import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import Opportunity, QueryIntent, ScoreBreakdown
from src.ranking import (
    _calculate_deadline_score,
    _calculate_level_score,
    _calculate_opportunity_score,
    _calculate_penalties,
    _calculate_relevance_score,
    _calculate_remote_score,
    _calculate_type_score,
    _clamp,
    filter_and_rank_opportunities,
)


def _days(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


def _make_opp(
        id: str = "test",
        title: str = "Test Opportunity",
        type: str = "internship",
        tags: list[str] | None = None,
        skills: list[str] | None = None,
        level: str = "intermediate",
        remote: bool = False,
        deadline: str | None = None,
        description: str = "Это подробное описание тестовой возможности для студентов",
        source_url: str | None = "https://example.com",
) -> Opportunity:
    return Opportunity(
        id=id,
        title=title,
        type=type,
        topic_tags=tags or [],
        skills=skills or [],
        level=level,
        location="Москва",
        remote=remote,
        deadline=deadline,
        duration=None,
        description=description,
        source_name="test",
        source_url=source_url,
        collected_at="2026-04-24",
        is_live_api=False,
    )


def _make_intent(
        keywords: list[str] | None = None,
        is_beginner: bool = False,
        user_level: str | None = None,
        topics: list[str] | None = None,
        type_preferences: list[str] | None = None,
        wants_remote: bool = False,
        is_urgent: bool = False,
) -> QueryIntent:
    return QueryIntent(
        original="test query",
        keywords=keywords or [],
        is_beginner=is_beginner,
        user_level=user_level,
        topics=topics,
        type_preferences=type_preferences,
        wants_remote=wants_remote,
        is_urgent=is_urgent,
        live_query="python",
    )


def test_clamp_within_range():
    assert _clamp(50.0) == 50.0


def test_clamp_above_max():
    assert _clamp(150.0) == 100.0


def test_clamp_below_min():
    assert _clamp(-20.0) == 0.0


def test_relevance_keyword_in_title():
    opp = _make_opp(title="Python курс для начинающих")
    intent = _make_intent(keywords=["python"])
    score = _calculate_relevance_score(opp, intent)
    assert score >= 12


def test_relevance_keyword_only_in_description():
    opp = _make_opp(
        title="Образовательная программа",
        description="Изучите python с нуля за три месяца на практике",
    )
    intent = _make_intent(keywords=["python"])
    score = _calculate_relevance_score(opp, intent)
    assert score >= 5
    assert score < 12


def test_relevance_keyword_in_tags():
    opp = _make_opp(title="Стажировка", tags=["python", "ml"])
    intent = _make_intent(keywords=["python"])
    score = _calculate_relevance_score(opp, intent)
    assert score >= 8


def test_relevance_keyword_in_skills():
    opp = _make_opp(title="Стажировка", skills=["python", "docker"])
    intent = _make_intent(keywords=["python"])
    score = _calculate_relevance_score(opp, intent)
    assert score >= 6


def test_relevance_topic_overlap():
    opp = _make_opp(tags=["ml", "ai"])
    intent = _make_intent(topics=["ml", "ai"])
    score = _calculate_relevance_score(opp, intent)
    assert score >= 14


def test_relevance_title_beats_description():
    opp_title = _make_opp(title="Python разработчик")
    opp_desc = _make_opp(
        title="Стажировка",
        description="Работа с python и другими технологиями",
    )
    intent = _make_intent(keywords=["python"])
    assert _calculate_relevance_score(opp_title, intent) > _calculate_relevance_score(opp_desc, intent)


def test_relevance_capped_in_final_score():
    opp = _make_opp(
        title="Python ML AI машинное обучение нейросети",
        tags=["python", "ml", "ai", "dl", "nlp"],
        skills=["python", "ml", "pytorch"],
        description="Курс по машинному обучению с практическими заданиями",
    )
    intent = _make_intent(keywords=["python", "ml", "ai", "dl", "nlp"], topics=["python", "ml", "ai"])
    score_10, score_100, _, breakdown = _calculate_opportunity_score(opp, intent)
    assert breakdown.relevance_score <= 45.0
    assert score_100 <= 100.0
    assert score_10 <= 10.0


def test_type_exact_match():
    opp = _make_opp(type="internship")
    intent = _make_intent(type_preferences=["internship"])
    assert _calculate_type_score(opp, intent) == 20.0


def test_type_close_match():
    opp = _make_opp(type="course")
    intent = _make_intent(type_preferences=["program"])
    assert _calculate_type_score(opp, intent) == 10.0


def test_type_no_match():
    opp = _make_opp(type="hackathon")
    intent = _make_intent(type_preferences=["internship"])
    assert _calculate_type_score(opp, intent) == 0.0


def test_type_not_specified_neutral():
    opp = _make_opp(type="program")
    intent = _make_intent(type_preferences=None)
    assert _calculate_type_score(opp, intent) == 8.0


def test_level_beginner_beginner():
    opp = _make_opp(level="beginner")
    intent = _make_intent(is_beginner=True, user_level="beginner")
    assert _calculate_level_score(opp, intent) == 15.0


def test_level_beginner_intermediate():
    opp = _make_opp(level="intermediate")
    intent = _make_intent(is_beginner=True, user_level="beginner")
    assert _calculate_level_score(opp, intent) == 8.0


def test_level_beginner_advanced():
    opp = _make_opp(level="advanced")
    intent = _make_intent(is_beginner=True, user_level="beginner")
    assert _calculate_level_score(opp, intent) == 2.0


def test_level_intermediate_intermediate():
    opp = _make_opp(level="intermediate")
    intent = _make_intent(user_level="intermediate")
    assert _calculate_level_score(opp, intent) == 15.0


def test_level_advanced_advanced():
    opp = _make_opp(level="advanced")
    intent = _make_intent(user_level="advanced")
    assert _calculate_level_score(opp, intent) == 15.0


def test_level_unknown_user_neutral():
    opp = _make_opp(level="beginner")
    intent = _make_intent(user_level=None)
    assert _calculate_level_score(opp, intent) == 6.0


def test_level_is_beginner_flag_fallback():
    opp = _make_opp(level="beginner")
    intent = _make_intent(is_beginner=True, user_level=None)
    assert _calculate_level_score(opp, intent) == 15.0


def test_remote_match():
    opp = _make_opp(remote=True)
    intent = _make_intent(wants_remote=True)
    assert _calculate_remote_score(opp, intent) == 10.0


def test_remote_no_match():
    opp = _make_opp(remote=False)
    intent = _make_intent(wants_remote=True)
    assert _calculate_remote_score(opp, intent) == 0.0


def test_remote_preference_not_specified():
    opp = _make_opp(remote=False)
    intent = _make_intent(wants_remote=False)
    assert _calculate_remote_score(opp, intent) == 5.0


def test_remote_preference_not_specified_remote_opp():
    opp = _make_opp(remote=True)
    intent = _make_intent(wants_remote=False)
    assert _calculate_remote_score(opp, intent) == 5.0


def test_deadline_urgent_7days():
    opp = _make_opp(deadline=_days(5))
    assert _calculate_deadline_score(opp) == 10.0


def test_deadline_near_30days():
    opp = _make_opp(deadline=_days(20))
    assert _calculate_deadline_score(opp) == 7.0


def test_deadline_far_90days():
    opp = _make_opp(deadline=_days(60))
    assert _calculate_deadline_score(opp) == 4.0


def test_deadline_very_far():
    opp = _make_opp(deadline=_days(120))
    assert _calculate_deadline_score(opp) == 2.0


def test_deadline_unknown():
    opp = _make_opp(deadline=None)
    assert _calculate_deadline_score(opp) == 3.0


def test_deadline_expired_returns_zero():
    opp = _make_opp(deadline=_days(-10))
    assert _calculate_deadline_score(opp) == 0.0


def test_deadline_urgent_mode_5days():
    opp = _make_opp(deadline=_days(5))
    assert _calculate_deadline_score(opp, urgent=True) == 35.0


def test_penalty_past_deadline():
    opp = _make_opp(deadline=_days(-1))
    pen = _calculate_penalties(opp)
    assert pen <= -100.0


def test_penalty_short_description():
    opp = _make_opp(description="Короткое")
    pen = _calculate_penalties(opp)
    assert pen <= -5.0


def test_penalty_no_skills_no_tags():
    opp = _make_opp(tags=[], skills=[])
    pen = _calculate_penalties(opp)
    assert pen <= -5.0


def test_penalty_no_data_at_all():
    opp = _make_opp(
        description="Кор",
        tags=[],
        skills=[],
        source_url=None,
    )
    pen = _calculate_penalties(opp)
    assert pen <= -20.0


def test_penalty_good_opp_zero():
    opp = _make_opp(
        description="Это достаточно длинное описание чтобы не получить штраф",
        tags=["ml"],
        skills=["python"],
        source_url="https://example.com",
    )
    pen = _calculate_penalties(opp)
    assert pen == 0.0


def test_score_range_0_to_10():
    opp = _make_opp(tags=["ml"], skills=["python"], description="ML курс для начинающих по машинному обучению")
    intent = _make_intent(keywords=["ml", "python"], topics=["ml"])
    score_10, score_100, _, _ = _calculate_opportunity_score(opp, intent)
    assert 0.0 <= score_10 <= 10.0
    assert 0.0 <= score_100 <= 100.0


def test_score_breakdown_returned():
    opp = _make_opp(tags=["ml"])
    intent = _make_intent(topics=["ml"])
    _, _, _, breakdown = _calculate_opportunity_score(opp, intent)
    assert isinstance(breakdown, ScoreBreakdown)
    assert breakdown.relevance_score >= 0
    assert breakdown.type_score >= 0
    assert breakdown.level_score >= 0
    assert breakdown.remote_score >= 0
    assert breakdown.deadline_score >= 0


def test_score_expired_deadline_near_zero():
    opp = _make_opp(deadline=_days(-5), tags=["ml"])
    intent = _make_intent(topics=["ml"])
    score_10, score_100, _, _ = _calculate_opportunity_score(opp, intent)
    assert score_10 == 0.0
    assert score_100 == 0.0


def test_score_perfect_match_high():
    opp = _make_opp(
        title="Машинное обучение для начинающих",
        type="program",
        tags=["ml", "python"],
        skills=["python", "sklearn"],
        level="beginner",
        remote=True,
        deadline=_days(5),
        description="Полный курс по машинному обучению с практическими заданиями и проектами",
    )
    intent = _make_intent(
        keywords=["машинное", "обучение", "python"],
        topics=["ml", "python"],
        type_preferences=["program"],
        is_beginner=True,
        user_level="beginner",
        wants_remote=True,
    )
    score_10, _, _, _ = _calculate_opportunity_score(opp, intent)
    assert score_10 >= 7.0


def test_top_k_respected():
    opps = [_make_opp(id=str(i), title=f"ML Program {i}", tags=["ml"]) for i in range(10)]
    intent = _make_intent(topics=["ml"])
    ranked, _ = filter_and_rank_opportunities(opps, intent, top_k=3)
    assert len(ranked) <= 3


def test_empty_input():
    ranked, call_repr = filter_and_rank_opportunities([], _make_intent())
    assert ranked == []
    assert "filter_and_rank_opportunities" in call_repr


def test_expired_filtered_out():
    opps = [
        _make_opp("expired", "ML курс", deadline=_days(-10), tags=["ml"]),
        _make_opp("active", "Python программа", tags=["python"]),
    ]
    intent = _make_intent(topics=["ml", "python"])
    ranked, _ = filter_and_rank_opportunities(opps, intent, top_k=5)
    ids = [r.opportunity.id for r in ranked]
    assert "expired" not in ids


def test_beginner_opp_ranked_higher_for_beginner():
    opps = [
        _make_opp("adv", "ML Research", level="advanced", tags=["ml"]),
        _make_opp("beg", "ML для начинающих", level="beginner", tags=["ml"]),
    ]
    intent = _make_intent(is_beginner=True, user_level="beginner", topics=["ml"])
    ranked, _ = filter_and_rank_opportunities(opps, intent, top_k=2)
    assert ranked[0].opportunity.id == "beg"


def test_exact_type_ranked_higher():
    opps = [
        _make_opp("hack", "AI Hackathon", type="hackathon", tags=["ai"]),
        _make_opp("prog", "AI Program", type="program", tags=["ai"]),
    ]
    intent = _make_intent(topics=["ai"], type_preferences=["program"])
    ranked, _ = filter_and_rank_opportunities(opps, intent, top_k=2)
    assert ranked[0].opportunity.id == "prog"


def test_remote_ranked_higher_when_requested():
    opp_onsite = _make_opp("onsite", "ML стажировка офлайн", remote=False, tags=["ml"])
    opp_remote = _make_opp("remote", "ML стажировка онлайн", remote=True, tags=["ml"])
    intent = _make_intent(topics=["ml"], wants_remote=True)
    score_onsite, _, _, _ = _calculate_opportunity_score(opp_onsite, intent)
    score_remote, _, _, _ = _calculate_opportunity_score(opp_remote, intent)
    assert score_remote > score_onsite


def test_keyword_title_match_scores_higher():
    opps = [
        _make_opp("a", "Образовательная программа", description="Изучите python с нуля"),
        _make_opp("b", "Python разработчик", tags=["python"]),
    ]
    intent = _make_intent(keywords=["python"])
    ranked, _ = filter_and_rank_opportunities(opps, intent, top_k=2)
    assert ranked[0].opportunity.id == "b"


def test_score_stored_in_scored_opportunity():
    opp = _make_opp(tags=["ml"])
    intent = _make_intent(topics=["ml"])
    ranked, _ = filter_and_rank_opportunities([opp], intent, top_k=1)
    if ranked:
        assert 0.0 <= ranked[0].score <= 10.0
        assert ranked[0].score_100 >= 0.0
        assert ranked[0].breakdown is not None


def test_urgent_mode_deadline_weighted_more():
    opp_near = _make_opp("near", "ML курс", tags=["ml"], deadline=_days(3))
    opp_normal = _make_opp("normal", "ML курс 2", tags=["ml"], deadline=_days(80))

    intent_normal = _make_intent(topics=["ml"], is_urgent=False)
    intent_urgent = _make_intent(topics=["ml"], is_urgent=True)

    ranked_normal, _ = filter_and_rank_opportunities([opp_near, opp_normal], intent_normal, top_k=2)
    ranked_urgent, _ = filter_and_rank_opportunities([opp_near, opp_normal], intent_urgent, top_k=2)

    if ranked_urgent:
        assert ranked_urgent[0].opportunity.id == "near"


def test_call_repr_contains_function_name():
    _, call_repr = filter_and_rank_opportunities([], _make_intent())
    assert "filter_and_rank_opportunities" in call_repr
