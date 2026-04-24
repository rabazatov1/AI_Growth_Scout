from src.config import settings


def llm_complete(system: str, user: str, temperature: float = 0.3) -> str | None:
    if not settings.OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=2000,
        )
        return response.choices[0].message.content
    except Exception:
        return None


def llm_available() -> bool:
    return bool(settings.OPENAI_API_KEY)
