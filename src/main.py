import argparse
import sys
from pathlib import Path

import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent import AgentRunner
from src.models import AgentResponse, QueryRequest

console = Console()


def _print_response(response: AgentResponse) -> None:
    console.rule("[bold cyan]AI Growth Scout — Навигатор для студентов[/bold cyan]")
    console.print()

    for tool_call in response.tools_used:
        console.print(f"  [dim cyan]\\[инструмент][/dim cyan] {tool_call}")
    console.print()

    console.print(Panel(response.answer, title="[bold green]Ответ агента[/bold green]", border_style="green"))

    if response.opportunities:
        table = Table(
            box=box.ROUNDED,
            show_lines=True,
            title="[bold]Подобранные возможности[/bold]",
            title_style="bold white",
        )
        table.add_column("Название", style="bold", max_width=40)
        table.add_column("Тип", style="cyan", max_width=14)
        table.add_column("Уровень", style="yellow", max_width=14)
        table.add_column("Дедлайн", style="magenta", max_width=12)
        table.add_column("Балл", justify="right", style="green", max_width=7)
        table.add_column("Почему", max_width=35)
        table.add_column("Источник", style="dim", max_width=20)

        for sr in response.opportunities:
            opp = sr.opportunity
            src = opp.source_name
            if opp.source_url:
                src = f"[link={opp.source_url}]{src}[/link]"
            table.add_row(
                opp.title,
                opp.type,
                opp.level,
                opp.deadline or "—",
                f"{sr.score:.1f}",
                sr.reason,
                src,
            )

        console.print(table)

    if response.caveats:
        console.print("\n[bold yellow]Предупреждения:[/bold yellow]")
        for c in response.caveats:
            console.print(f"  [yellow]•[/yellow] {c}")

    console.print()


def _run_cli(args: argparse.Namespace) -> None:
    from pydantic import ValidationError

    runner = AgentRunner()
    try:
        request = QueryRequest(
            query=args.query,
            top_k=args.top_k,
            offline=args.offline,
            save_json=args.save_json,
        )
    except ValidationError as e:
        for err in e.errors():
            field = err["loc"][0] if err["loc"] else "поле"
            msg = err["msg"]
            console.print(f"[bold red]Ошибка параметра «{field}»:[/bold red] {msg}")
        raise SystemExit(1)
    console.print(f"\n[bold]Запрос:[/bold] {args.query}")
    console.print(f"[dim]top_k={args.top_k}  offline={args.offline}  save_json={args.save_json}[/dim]\n")

    response = runner.run(request)
    _print_response(response)


def _run_api(host: str = "127.0.0.1", port: int = 8000) -> None:
    uvicorn.run("src.api:app", host=host, port=port, reload=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI Growth Scout — агент-навигатор по возможностям для студентов",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python -m src.main --query "курсы по ML для начинающих"
  python -m src.main --query "хакатоны по AI в мае" --offline
  python -m src.main --query "программы по data science" --top-k 7
  python -m src.main --query "стажировки в Яндексе" --save-json
  python -m src.main --serve
        """,
    )
    parser.add_argument("--query", "-q", type=str, help="Запрос на естественном языке")
    parser.add_argument("--top-k", type=int, default=5, dest="top_k", help="Количество результатов (по умолчанию: 5)")
    parser.add_argument("--offline", action="store_true",
                        help="Пропустить Stepik API, использовать только кураторские данные")
    parser.add_argument("--save-json", action="store_true", dest="save_json", help="Сохранить результаты в data/cache/")
    parser.add_argument("--serve", action="store_true", help="Запустить FastAPI-сервер вместо CLI")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    if args.serve:
        _run_api(host=args.host, port=args.port)
        return

    if not args.query:
        parser.print_help()
        sys.exit(1)

    _run_cli(args)


if __name__ == "__main__":
    main()
