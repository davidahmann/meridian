import typer
import uvicorn
import os
import sys
import importlib.util
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.table import Table
from datetime import datetime
from .core import FeatureStore
from .server import create_app


app = typer.Typer()
console = Console()


@app.command(name="events")
def events_cmd(
    action: str = typer.Argument(..., help="Action: listen"),
    stream: str = typer.Option("meridian_events", help="Stream key to listen to"),
    count: int = typer.Option(10, help="Number of events to fetch per poll"),
    redis_url: str = typer.Option(
        None, envvar="MERIDIAN_REDIS_URL", help="Redis URL Override"
    ),
) -> None:
    """
    Manage or listen to Meridian events.
    Usage: meridian events listen --stream=my_stream
    """
    if action != "listen":
        console.print(f"[bold red]Unknown action:[/bold red] {action}")
        raise typer.Exit(1)

    import asyncio
    from redis.asyncio import Redis

    url = redis_url or os.getenv("MERIDIAN_REDIS_URL") or "redis://localhost:6379"

    async def listen_loop() -> None:
        console.print(f"[green]Listening to stream:[/green] {stream} on {url}")
        r = Redis.from_url(url, decode_responses=True)
        last_id = "$"

        try:
            while True:
                # XREAD block=0 means block indefinitely until new item
                streams = await r.xread({stream: last_id}, count=1, block=0)
                if not streams:
                    continue

                for stream_name, messages in streams:
                    for msg_id, fields in messages:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        console.print(
                            f"[{timestamp}] [bold cyan]{msg_id}[/bold cyan]: {fields}"
                        )
                        last_id = msg_id
        except asyncio.CancelledError:
            pass
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
        finally:
            await r.aclose()  # type: ignore[attr-defined]

    try:
        asyncio.run(listen_loop())
    except KeyboardInterrupt:
        console.print("\nStopped.")


console = Console()


@app.callback()
def callback() -> None:
    """
    Meridian CLI
    """


@app.command(name="worker")
def worker_cmd(
    file: str = typer.Argument(
        ..., help="Path to the feature definition file (e.g., features.py)"
    ),
    redis_url: str = typer.Option(
        None, envvar="MERIDIAN_REDIS_URL", help="Redis URL Override"
    ),
) -> None:
    """
    Starts the Axiom background worker.
    """
    import asyncio
    from .worker import AxiomWorker

    # 1. Load Feature Definitions
    if not os.path.exists(file):
        console.print(f"[bold red]Error:[/bold red] File '{file}' not found.")
        raise typer.Exit(code=1)

    sys.path.append(os.getcwd())
    try:
        module_name = os.path.splitext(os.path.basename(file))[0]
        spec = importlib.util.spec_from_file_location(module_name, file)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

        # Find store instance
        store = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, FeatureStore):
                store = attr
                break

        if not store:
            console.print("[bold red]Error:[/bold red] No FeatureStore found in file.")
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[bold red]Error loading features:[/bold red] {e}")
        raise typer.Exit(code=1)

    console.print(Panel(f"Starting Axiom Worker for {file}...", style="bold green"))

    # Pass store to worker
    worker = AxiomWorker(redis_url=redis_url, store=store)
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        console.print("Worker stopped.")


@app.command(name="version")
def version() -> None:
    """
    Prints the Meridian version.
    """
    try:
        from importlib.metadata import version

        v = version("meridian-oss")
    except Exception:
        v = "unknown"
    console.print(f"Meridian OSS v{v}")


@app.command(name="serve")
def serve(
    file: str = typer.Argument(
        ..., help="Path to the feature definition file (e.g., features.py)"
    ),
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
    api_key: str = typer.Option(
        None, envvar="MERIDIAN_API_KEY", help="API Key for security"
    ),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
) -> None:
    """
    Starts the Meridian server.
    """
    if not os.path.exists(file):
        console.print(f"[bold red]Error:[/bold red] File '{file}' not found.")
        raise typer.Exit(code=1)

    console.print(
        Panel(
            f"Starting Meridian on http://{host}:{port}",
            title="Meridian",
            style="bold blue",
        )
    )

    # For now, we just print that we are starting.
    # In Epic 4 (Serving API), we will actually start the FastAPI server here.
    # For Epic 2, we just need to verify the CLI works and can load the file.

    # Simulate loading the file to register features
    sys.path.append(os.getcwd())

    try:
        # Import the module to execute the decorators and register features
        module_name = os.path.splitext(os.path.basename(file))[0]

        # Load module dynamically
        spec = importlib.util.spec_from_file_location(module_name, file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec for {file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Find FeatureStore instance in the module
        store = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, FeatureStore):
                store = attr
                break

        if not store:
            console.print(
                "[bold red]Error:[/bold red] No FeatureStore instance found in file."
            )
            raise typer.Exit(code=1)

        # Start scheduler
        store.start()

        # Set API key in env for the server to pick up
        if api_key:
            os.environ["MERIDIAN_API_KEY"] = api_key

        app = create_app(store)

        # Create Rich Layout
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3),
        )

        layout["header"].update(
            Panel(
                f"Meridian Feature Store | Serving {file} on http://{host}:{port}",
                style="bold white on blue",
            )
        )

        # Create a table for metrics
        def generate_metrics_table() -> Panel:
            table = Table(title="Live Metrics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")

            # Display basic static metrics (Real-time dashboard requires Epic 4.2)
            # In a real implementation, we'd read from a shared metrics buffer
            table.add_row("Status", "Running 🟢")
            table.add_row("Uptime", datetime.now().strftime("%H:%M:%S"))
            table.add_row("Entities", str(len(store.registry.entities)))
            table.add_row("Features", str(len(store.registry.features)))
            return Panel(table, title="System Status", border_style="green")

        layout["main"].update(generate_metrics_table())

        layout["footer"].update(Panel("Press Ctrl+C to stop", style="dim"))

        console.print(f"[green]Successfully loaded features from {file}[/green]")
        console.print(
            "Starting server... (TUI disabled for simple log output compatibility)"
        )

        # NOTE: Running uvicorn inside a Rich Live context is tricky because uvicorn takes over stdout.
        # For this MVP, we will just print the rich header and then run uvicorn.
        # A full TUI requires running uvicorn in a separate thread/process and capturing logs.

        console.print(layout)
        uvicorn.run(app, host=host, port=port)

    except Exception as e:
        console.print(f"[bold red]Error loading features:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="ui")
def ui(
    file: str = typer.Argument(
        ..., help="Path to the feature definition file (e.g., features.py)"
    ),
) -> None:
    """
    Launches the Meridian UI (Streamlit).
    """
    if not os.path.exists(file):
        console.print(f"[bold red]Error:[/bold red] File '{file}' not found.")
        raise typer.Exit(code=1)

    try:
        import streamlit.web.cli as stcli
    except ImportError:
        console.print(
            "[bold red]Error:[/bold red] Streamlit is not installed. "
            "Please run [green]pip install meridian[ui][/green] or [green]pip install streamlit[/green]."
        )
        raise typer.Exit(code=1)

    # Resolve absolute path to the UI script
    ui_script = os.path.join(os.path.dirname(__file__), "ui.py")

    # Construct the command args for streamlit
    # Format: streamlit run path/to/ui.py --server.headless=true --server.port=8501 -- path/to/features.py
    sys.argv = [
        "streamlit",
        "run",
        ui_script,
        "--server.headless=true",
        "--server.port=8501",
        "--",
        file,
    ]

    console.print(f"[green]Launching Meridian UI for {file}...[/green]")
    sys.exit(stcli.main())


@app.command(name="doctor")
def doctor() -> None:
    """
    Diagnose configuration and connectivity issues.
    """
    from .doctor import run_doctor

    run_doctor()


@app.command(name="context")
def context_cmd(
    ctx_id: str = typer.Argument(..., help="The Context ID to trace"),
    host: str = typer.Option("127.0.0.1", help="Meridian server host"),
    port: int = typer.Option(8000, help="Meridian server port"),
) -> None:
    """
    Fetch and display a context trace (RAG explanation).
    """
    import urllib.request
    import urllib.error
    import json

    url = f"http://{host}:{port}/context/{ctx_id}/explain"
    console.print(f"Fetching trace for [bold cyan]{ctx_id}[/bold cyan] from {url}...")

    if not url.lower().startswith(("http://", "https://")):
        console.print("[bold red]Error:[/bold red] Invalid URL scheme")
        raise typer.Exit(1)

    try:
        # Use standard lib to avoid extra dependencies for CLI
        req = urllib.request.Request(url)
        # Add API Key if present in env
        api_key = os.getenv("MERIDIAN_API_KEY")
        if api_key:
            req.add_header("X-API-Key", api_key)

        with urllib.request.urlopen(req) as response:  # nosec B310
            if response.status != 200:
                console.print(
                    f"[bold red]Error:[/bold red] Server returned {response.status}"
                )
                raise typer.Exit(1)

            data = json.loads(response.read().decode())

            # Pretty print with Rich
            console.print(
                Panel(
                    json.dumps(data, indent=2),
                    title=f"Context Trace: {ctx_id}",
                    border_style="green",
                )
            )

    except urllib.error.URLError as e:
        console.print(
            f"[bold red]Connection Failed:[/bold red] {e}. Is the server running?"
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command(name="index")
def index_cmd(
    action: str = typer.Argument(..., help="Action: create, status"),
    name: str = typer.Argument(..., help="Name of the index"),
    dimension: int = typer.Option(1536, help="Vector dimension (create only)"),
    postgres_url: str = typer.Option(
        None, envvar="MERIDIAN_POSTGRES_URL", help="Postgres URL Override"
    ),
) -> None:
    """
    Manage vector indexes.
    Usage:
      meridian index create my_index --dimension=1536
      meridian index status my_index
    """
    import asyncio
    from .store.postgres import PostgresOfflineStore
    from sqlalchemy import text

    url = postgres_url or os.getenv("MERIDIAN_POSTGRES_URL")
    if not url:
        console.print("[bold red]Error:[/bold red] MERIDIAN_POSTGRES_URL not set.")
        raise typer.Exit(1)

    async def run_action() -> None:
        try:
            store = PostgresOfflineStore(url)

            if action == "create":
                console.print(
                    f"Creating index [bold]{name}[/bold] (dim={dimension})..."
                )
                await store.create_index_table(name, dimension)
                console.print(f"[green]Index '{name}' created successfully.[/green]")

            elif action == "status":
                table = f"meridian_index_{name}"
                async with store.engine.connect() as conn:  # type: ignore[no-untyped-call]
                    # Check if exists
                    exists = await conn.execute(
                        text(f"SELECT to_regclass('public.{table}')")
                    )
                    if not exists.scalar():
                        console.print(
                            f"[red]Index table '{table}' does not exist.[/red]"
                        )
                        return

                    # Count rows
                    res = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))  # nosec
                    count = res.scalar()
                    console.print(f"Index: [bold]{name}[/bold]")
                    console.print(f"Table: {table}")
                    console.print(f"Rows:  [cyan]{count}[/cyan]")

            else:
                console.print(f"[red]Unknown action: {action}[/red]")

            await store.engine.dispose()  # type: ignore[no-untyped-call]

        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(1)

    asyncio.run(run_action())


if __name__ == "__main__":
    app()
