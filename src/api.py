from datetime import date

from fastapi import FastAPI

from src.agent import AgentRunner
from src.llm import llm_available
from src.config import settings
from src.models import AgentResponse, HealthResponse, QueryRequest, SourceInfo

app = FastAPI(
    title="AI Growth Scout",
    description="Агент-навигатор для студентов: курсы, хакатоны, стажировки и программы в IT.",
    version="1.0.0",
)

runner = AgentRunner()


@app.get("/health", response_model=HealthResponse)
def health():
    provider = "нет"
    if settings.OPENAI_API_KEY:
        if "groq" in settings.OPENAI_BASE_URL:
            provider = f"Groq ({settings.OPENAI_MODEL})"
        else:
            provider = "OpenAI"

    configured = llm_available()
    llm_note = (
        "ключ настроен, работоспособность не проверялась"
        if configured
        else "ключ не настроен — используется правиловая система"
    )

    return HealthResponse(
        status="ok",
        llm_configured=configured,
        llm_provider=provider,
        llm_note=llm_note,
    )


@app.post("/query", response_model=AgentResponse)
def query(request: QueryRequest):
    return runner.run(request)


@app.get("/sources", response_model=list[SourceInfo])
def sources():
    today = date.today().isoformat()
    return [
        SourceInfo(
            name="Stepik API",
            type="live_api",
            url="https://stepik.org/api/courses",
            notes="Публичный API курсов. Бесплатные и платные курсы на русском и английском.",
            collected_at=today,
        ),
        SourceInfo(
            name="Кураторский датасет (opportunities_curated.json)",
            type="static_file",
            url=None,
            notes=(
                "Ручная подборка из 16 записей: "
                "7 стажировок (Яндекс, Сбер, Selectel, YADRO, MTS Tech, Т-Старт, Газпром нефть), "
                "5 курсов (mlcourse.ai, Hexlet Frontend/Python, Karpov.Courses, Нетология), "
                "2 хакатона (MOEX AI, Город IT:HACK), "
                "2 программы (ШАД, Яндекс Лицей). Обновляется вручную."
            ),
            collected_at="2026-04-24",
        ),
        SourceInfo(
            name="Groq / LLM",
            type="llm",
            url="https://console.groq.com",
            notes=(
                "Используется для умного разбора запроса и генерации ответа (Llama 3.3 70B). "
                "Требует OPENAI_API_KEY в .env (ключ с console.groq.com). Совместим с OpenAI и другими провайдерами."
            ),
            collected_at=today,
        ),
    ]
