import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils import (
    build_stepik_query,
    deduplicate,
    detect_beginner,
    detect_remote,
    detect_topics,
    detect_type_preferences,
    extract_keywords,
    normalize_text,
    should_use_live_api,
)
from src.tools.stepik_api import _detect_level, _extract_topics, _normalize_course


def test_normalize_text_lowercases():
    assert normalize_text("Machine Learning") == "machine learning"


def test_normalize_text_removes_punctuation():
    result = normalize_text("Hello, world!")
    assert "," not in result
    assert "!" not in result


def test_extract_keywords_short_words_excluded():
    keywords = extract_keywords("найди мне стажировку по AI")
    assert "мне" not in keywords


def test_extract_keywords_deduplicates():
    keywords = extract_keywords("ml ml machine learning")
    assert len(keywords) == len(set(keywords))


def test_detect_beginner_english():
    assert detect_beginner("no experience required") is True
    assert detect_beginner("senior ML engineer") is False


def test_detect_beginner_russian():
    assert detect_beginner("без опыта работы") is True
    assert detect_beginner("начинающим разработчикам") is True
    assert detect_beginner("продвинутый ML") is False


def test_detect_remote():
    assert detect_remote("remote internship") is True
    assert detect_remote("онлайн курс") is True
    assert detect_remote("офис в Москве") is False


def test_detect_topics_ml():
    assert "ml" in detect_topics("machine learning internship")


def test_detect_topics_cv():
    assert "cv" in detect_topics("computer vision hackathon")


def test_detect_topics_nlp():
    assert "nlp" in detect_topics("NLP research program")


def test_detect_type_internship():
    prefs = detect_type_preferences("найди стажировку в AI")
    assert "internship" in prefs


def test_detect_type_hackathon():
    prefs = detect_type_preferences("лучший хакатон для новичков")
    assert "hackathon" in prefs


def test_detect_type_course():
    prefs = detect_type_preferences("курсы по python")
    assert "course" in prefs


def test_deduplicate_removes_duplicates():
    items = [{"title": "A"}, {"title": "B"}, {"title": "A"}]
    unique = deduplicate(items, lambda x: x["title"])
    assert len(unique) == 2
    assert unique[0]["title"] == "A"
    assert unique[1]["title"] == "B"


def test_build_stepik_query_with_topics():
    q = build_stepik_query("хочу учиться ML", ["ml"])
    assert q == "машинное обучение"


def test_build_stepik_query_python_fallback():
    q = build_stepik_query("python разработка", [])
    assert "python" in q.lower()


def test_build_stepik_query_default():
    q = build_stepik_query("что-то непонятное", [])
    assert isinstance(q, str) and len(q) > 0


def test_should_use_live_api_course_triggers():
    assert should_use_live_api("курсы по python", []) is True
    assert should_use_live_api("хочу учиться ml с нуля", []) is True


def test_should_use_live_api_hackathon_only():
    assert should_use_live_api("хакатоны по AI", ["hackathon"]) is False


def test_should_use_live_api_default_true():
    assert should_use_live_api("что-то в IT", []) is True


def test_stepik_detect_level_beginner():
    assert _detect_level("Введение в Python для начинающих", "") == "beginner"
    assert _detect_level("Python с нуля", "") == "beginner"


def test_stepik_detect_level_advanced():
    assert _detect_level("Продвинутое машинное обучение", "") == "advanced"


def test_stepik_detect_level_default():
    assert _detect_level("Курс по анализу данных", "") == "intermediate"


def test_stepik_extract_topics_ml():
    topics = _extract_topics("Машинное обучение на Python", "")
    assert "ml" in topics


def test_stepik_extract_topics_python():
    topics = _extract_topics("Python для начинающих", "")
    assert "python" in topics


def test_stepik_extract_topics_default():
    topics = _extract_topics("Непонятный курс", "")
    assert topics == ["programming"]


def test_stepik_normalize_course():
    raw = {
        "id": 123,
        "title": "Python для начинающих",
        "summary": "Курс для новичков",
        "is_paid": False,
    }
    opp = _normalize_course(raw)
    assert opp.id == "stepik_123"
    assert opp.title == "Python для начинающих"
    assert opp.level == "beginner"
    assert opp.remote is True
    assert opp.is_live_api is True
    assert "python" in opp.topic_tags
    assert opp.source_url == "https://stepik.org/course/123"
