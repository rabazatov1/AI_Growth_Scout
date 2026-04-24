import json

from src.llm import llm_available, llm_complete
from src.models import AgentResponse, QueryIntent, QueryRequest, ScoredOpportunity
from src.prompts import ANSWER_SYSTEM, INTENT_SYSTEM, answer_user_prompt, intent_user_prompt
from src.ranking import filter_and_rank_opportunities
from src.tools.curated_loader import load_curated_opportunities
from src.tools.exporter import export_results_to_json
from src.tools.stepik_api import search_stepik_courses
from src.utils import (
    build_stepik_query,
    detect_beginner,
    detect_remote,
    detect_topics,
    detect_type_preferences,
    detect_urgent,
    extract_keywords,
    should_use_live_api,
)


def _parse_intent_llm(query: str) -> QueryIntent | None:
    try:
        raw = llm_complete(INTENT_SYSTEM, intent_user_prompt(query), temperature=0.1)
        if not raw:
            return None
        raw = raw.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:-1])
        data = json.loads(raw)
        raw_keywords = [k for k in data.get("keywords", []) if len(k) > 2]
        raw_live_query = data.get("live_query", "программирование")
        short_live_query = " ".join(raw_live_query.split()[:3])
        is_beginner = data.get("is_beginner", False)
        type_prefs = data.get("type_preferences") or None
        return QueryIntent(
            original=query,
            keywords=raw_keywords,
            is_beginner=is_beginner,
            user_level="beginner" if is_beginner else None,
            type_preferences=type_prefs,
            topics=data.get("topics") or None,
            wants_remote=data.get("wants_remote", False),
            is_urgent=detect_urgent(query),
            live_query=short_live_query,
            use_live_api=should_use_live_api(query, type_prefs),
        )
    except Exception:
        return None


def _parse_intent_rules(query: str) -> QueryIntent:
    keywords = extract_keywords(query)
    topics = detect_topics(query)
    type_prefs = detect_type_preferences(query)
    is_beginner = detect_beginner(query)

    return QueryIntent(
        original=query,
        keywords=keywords,
        is_beginner=is_beginner,
        user_level="beginner" if is_beginner else None,
        type_preferences=type_prefs or None,
        topics=topics or None,
        wants_remote=detect_remote(query),
        is_urgent=detect_urgent(query),
        live_query=build_stepik_query(query, topics),
        use_live_api=should_use_live_api(query, type_prefs),
    )


def _build_opportunities_summary(ranked: list[ScoredOpportunity]) -> str:
    lines = []
    for i, item in enumerate(ranked, 1):
        opp = item.opportunity
        line = (
            f"{i}. {opp.title} ({opp.type}) — {opp.source_name}\n"
            f"   Теги: {', '.join(opp.topic_tags)}, уровень: {opp.level}\n"
            f"   Дедлайн: {opp.deadline or 'не указан'}\n"
            f"   Ссылка: {opp.source_url or '—'}\n"
            f"   Оценка релевантности: {item.score:.1f} ({item.reason})"
        )
        lines.append(line)
    return "\n\n".join(lines)


def _generate_answer_llm(
        query: str,
        ranked: list[ScoredOpportunity],
        tools_used: list[str],
) -> str | None:
    summary = _build_opportunities_summary(ranked)
    tools_str = "\n".join(f"  - {t}" for t in tools_used)
    user_msg = answer_user_prompt(query, summary) + f"\n\nИспользованные инструменты:\n{tools_str}"
    return llm_complete(ANSWER_SYSTEM, user_msg, temperature=0.4)


def _generate_answer_rules(
        query: str,
        ranked: list[ScoredOpportunity],
        tools_used: list[str],
) -> str:
    if not ranked:
        return (
            "По вашему запросу ничего не найдено. "
            "Попробуйте уточнить тему (например: python, ML, хакатон) "
            "или запустите без флага --offline для поиска курсов на Stepik."
        )

    lines = [f"По запросу «{query}» найдено {len(ranked)} возможностей:\n"]
    for i, item in enumerate(ranked, 1):
        opp = item.opportunity
        deadline_str = f"дедлайн: {opp.deadline}" if opp.deadline else "дедлайн не указан"
        lines.append(
            f"{i}. {opp.title}\n"
            f"   Тип: {opp.type} | Уровень: {opp.level} | {deadline_str}\n"
            f"   Источник: {opp.source_name}\n"
            f"   Почему подходит: {item.reason}\n"
            f"   Ссылка: {opp.source_url or '—'}"
        )

    lines.append(f"\nИспользованные инструменты: {', '.join(tools_used)}")
    return "\n".join(lines)


class AgentRunner:
    def run(self, request: QueryRequest) -> AgentResponse:
        tools_used: list[str] = []
        caveats: list[str] = []
        all_opportunities = []

        if llm_available():
            intent = _parse_intent_llm(request.query) or _parse_intent_rules(request.query)
        else:
            intent = _parse_intent_rules(request.query)

        stepik_found: int = 0
        stepik_query: str = ""

        if not request.offline and intent.use_live_api:
            if not intent.live_query.strip():
                caveats.append(
                    "Запрос не содержит распознаваемых ключевых слов — "
                    "поиск на Stepik пропущен, используются только кураторские данные"
                )
            else:
                stepik_results, stepik_call = search_stepik_courses(
                    query=intent.live_query,
                    limit=15,
                )
                tools_used.append(stepik_call)
                if stepik_results:
                    all_opportunities.extend(stepik_results)
                    stepik_found = len(stepik_results)
                    stepik_query = intent.live_query
                else:
                    caveats.append(
                        "Stepik API не вернул результатов или временно недоступен — "
                        "используются только кураторские данные"
                    )
        elif request.offline:
            caveats.append("Офлайн-режим: Stepik API пропущен")
        else:
            caveats.append(
                "Поиск курсов на Stepik пропущен — запрос относится к конкретным "
                "возможностям (хакатоны, стажировки, программы)"
            )

        curated, curated_call = load_curated_opportunities()
        tools_used.append(curated_call)
        if curated:
            all_opportunities.extend(curated)
        else:
            caveats.append("Кураторский датасет не найден или пустой")

        ranked, rank_call = filter_and_rank_opportunities(
            all_opportunities, intent, top_k=request.top_k
        )
        tools_used.append(rank_call)

        if stepik_found > 0:
            stepik_in_top = sum(1 for r in ranked if r.opportunity.is_live_api)
            msg = f"Живые данные Stepik: найдено {stepik_found} курсов по запросу «{stepik_query}»"
            if stepik_in_top == 0:
                msg += " — в топ не вошли (низкая релевантность для этого запроса)"
            elif stepik_in_top < stepik_found:
                msg += f", в топ вошли {stepik_in_top}"
            caveats.append(msg)

        if request.save_json:
            _, export_call = export_results_to_json(ranked)
            tools_used.append(export_call)

        if llm_available():
            llm_answer = _generate_answer_llm(request.query, ranked, tools_used)
            if llm_answer:
                answer = llm_answer
            else:
                answer = _generate_answer_rules(request.query, ranked, tools_used)
                caveats.append(
                    "LLM недоступен (ошибка API) — ответ формируется по правилам"
                )
        else:
            answer = _generate_answer_rules(request.query, ranked, tools_used)
            caveats.append(
                "LLM не настроен — ответ формируется по правилам "
                "(добавьте OPENAI_API_KEY в .env для умных ответов)"
            )

        return AgentResponse(
            answer=answer,
            opportunities=ranked,
            tools_used=tools_used,
            caveats=caveats,
            query=request.query,
        )
