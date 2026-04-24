from datetime import date

import requests

from src.models import Opportunity


STEPIK_API_URL = "https://stepik.org/api/courses"
COLLECTED_AT = date.today().isoformat()

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "ml": ["machine learning", "машинное обучение", "sklearn", "scikit"],
    "dl": ["deep learning", "глубокое обучение", "нейронн", "neural", "pytorch", "tensorflow"],
    "data_science": ["data science", "анализ данных", "pandas", "numpy", "статистик"],
    "cv": ["computer vision", "компьютерное зрение", "opencv"],
    "nlp": ["nlp", "обработка текст", "natural language", "bert", "трансформ"],
    "python": ["python", "питон"],
    "ai": ["artificial intelligence", "искусственный интеллект", "нейросет"],
    "algorithms": ["алгоритм", "структур", "algorithm", "leetcode"],
}


def _detect_level(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    if any(w in text for w in ("начинающ", "нуля", "основы", "введение", "базов",
                                "beginner", "intro", "первый", "нулевой", "старт")):
        return "beginner"
    if any(w in text for w in ("продвинут", "advanced", "expert", "глубок", "углублённ", "профессион")):
        return "advanced"
    return "intermediate"


def _extract_topics(title: str, summary: str) -> list[str]:
    text = (title + " " + summary).lower()
    topics = [topic for topic, keywords in TOPIC_KEYWORDS.items()
              if any(kw in text for kw in keywords)]
    return topics or ["programming"]


def _normalize_course(course: dict) -> Opportunity:
    title = course.get("title") or "Без названия"
    summary = (course.get("summary") or "").strip()
    course_id = course.get("id", "")
    is_paid = course.get("is_paid", False)

    return Opportunity(
        id=f"stepik_{course_id}",
        title=title,
        type="course",
        topic_tags=_extract_topics(title, summary),
        level=_detect_level(title, summary),
        location="Онлайн",
        remote=True,
        deadline=None,
        duration=None,
        skills=[],
        description=summary[:300] or None,
        source_name="Stepik" + (" (платный)" if is_paid else " (бесплатный)"),
        source_url=f"https://stepik.org/course/{course_id}",
        collected_at=COLLECTED_AT,
        is_live_api=True,
    )


def search_stepik_courses(
    query: str,
    limit: int = 15,
) -> tuple[list[Opportunity], str]:
    call_repr = f"search_stepik_courses(query={query!r}, limit={limit})"

    try:
        response = requests.get(
            STEPIK_API_URL,
            params={"search": query, "page": 1},
            headers={"User-Agent": "AIGrowthScout/1.0"},
            timeout=10,
        )
        response.raise_for_status()
        courses = response.json().get("courses", [])
        free_first = sorted(courses, key=lambda c: c.get("is_paid", True))
        opportunities = [_normalize_course(c) for c in free_first[:limit]]
        return opportunities, call_repr
    except requests.Timeout:
        return [], call_repr
    except requests.RequestException:
        return [], call_repr
