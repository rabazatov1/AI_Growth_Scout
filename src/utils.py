import re
import unicodedata
from datetime import date


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    return re.sub(r"[^\w\s]", " ", text)


TECH_KEYWORDS = {
    "python", "ml", "machine learning", "deep learning", "nlp", "computer vision",
    "data science", "neural", "ai", "pytorch", "tensorflow", "keras", "sql",
    "машинное обучение", "нейронн", "данных", "анализ", "программирование",
    "разработка", "backend", "frontend", "алгоритм", "стажировка", "хакатон",
    "курс", "обучение", "школа", "искусственный интеллект",
}


def extract_keywords(query: str) -> list[str]:
    norm = normalize_text(query)
    words = norm.split()
    found = [w for w in words if len(w) > 3]
    bigrams = [f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)]
    result = []
    for term in found + bigrams:
        if any(kw in term for kw in TECH_KEYWORDS):
            result.append(term)
    return list(dict.fromkeys(result)) or words[:5]


BEGINNER_TRIGGERS = {
    "beginner", "junior", "no experience", "без опыта", "нет опыта", "начинающий",
    "начинающим", "начинающих", "начинающего", "новичок", "новичкам", "с нуля",
    "нулевой", "первый курс", "первокурсник", "только начинаю", "хочу начать",
    "без знаний", "базовые знания", "основы",
}


def detect_beginner(query: str) -> bool:
    norm = normalize_text(query)
    return any(trigger in norm for trigger in BEGINNER_TRIGGERS)


REMOTE_TRIGGERS = {"remote", "онлайн", "online", "удалённо", "дистанционно", "из дома"}


def detect_remote(query: str) -> bool:
    norm = normalize_text(query)
    return any(trigger in norm for trigger in REMOTE_TRIGGERS)


TYPE_MAP = {
    "стажировк": "internship",
    "internship": "internship",
    "хакатон": "hackathon",
    "hackathon": "hackathon",
    "курс": "course",
    "course": "course",
    "программ": "program",
    "обучен": "course",
}


def detect_type_preferences(query: str) -> list[str]:
    norm = normalize_text(query)
    found = []
    for trigger, type_val in TYPE_MAP.items():
        if trigger in norm and type_val not in found:
            found.append(type_val)
    return found


TOPIC_TRIGGERS = {
    "ml": ["ml", "machine learning", "машинное обучение", "машинному обучению"],
    "ai": ["ai", "artificial intelligence", "искусственный интеллект", "нейросет"],
    "dl": ["deep learning", "глубокое обучение", "нейронн"],
    "cv": ["computer vision", "компьютерное зрение", "opencv"],
    "nlp": ["nlp", "natural language", "обработка текст", "bert"],
    "data_science": ["data science", "анализ данных", "pandas"],
    "python": ["python", "питон"],
    "rl": ["reinforcement learning", "reinforcement", "rl "],
    "algorithms": ["алгоритм", "algorithm"],
}


def detect_topics(query: str) -> list[str]:
    norm = normalize_text(query)
    return [topic for topic, triggers in TOPIC_TRIGGERS.items()
            if any(t in norm for t in triggers)]


def days_until(deadline: str | None) -> int | None:
    if not deadline:
        return None
    try:
        d = date.fromisoformat(deadline)
        return (d - date.today()).days
    except ValueError:
        return None


def deduplicate(items: list, key_fn) -> list:
    seen = set()
    result = []
    for item in items:
        k = key_fn(item)
        if k not in seen:
            seen.add(k)
            result.append(item)
    return result


TOPIC_QUERY_MAP = {
    "ml": "машинное обучение",
    "dl": "глубокое обучение",
    "cv": "компьютерное зрение",
    "nlp": "обработка текста",
    "data_science": "анализ данных",
    "ai": "искусственный интеллект",
    "python": "python",
    "algorithms": "алгоритмы",
}

COURSE_TRIGGERS = {
    "курс", "курсы", "учиться", "обучение", "с нуля", "изучить",
    "научиться", "course", "learn", "tutorial", "освоить", "изучение", "учить",
}

PURE_OFFLINE_TYPES = {"hackathon", "internship"}


def build_stepik_query(query: str, topics: list[str]) -> str:
    if topics:
        return TOPIC_QUERY_MAP.get(topics[0], topics[0])
    norm = normalize_text(query)
    for kw, ru in [("python", "python"), ("ml", "машинное обучение"),
                   ("ai", "искусственный интеллект"), ("data", "анализ данных")]:
        if kw in norm:
            return ru
    return "программирование"


URGENT_TRIGGERS = {
    "скоро дедлайн", "дедлайн скоро", "горящ", "срочно", "успеть подать",
    "что сдать", "что успеть", "горящие", "прямо сейчас", "этой неделе",
    "expires soon", "deadline soon", "urgent",
}


def detect_urgent(query: str) -> bool:
    norm = normalize_text(query)
    return any(trigger in norm for trigger in URGENT_TRIGGERS)


def should_use_live_api(query: str, type_prefs: list[str] | None) -> bool:
    norm = normalize_text(query)
    if any(t in norm for t in COURSE_TRIGGERS):
        return True
    if type_prefs and all(t in PURE_OFFLINE_TYPES for t in type_prefs):
        return False
    return True
