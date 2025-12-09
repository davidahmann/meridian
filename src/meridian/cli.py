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
def callback(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
) -> None:
    """
    Meridian CLI
    """
    if verbose:
        import logging

        # Configure standard logging to DEBUG
        logging.basicConfig(level=logging.DEBUG, force=True)

        # Configure structlog to print to console with colors if possible
        # For now, we assume simple standard logging config suffices for "verbose"
        console.print("[dim]Verbose output enabled[/dim]")


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


@app.command(name="setup")
def setup(
    dir: str = typer.Argument(".", help="Directory to create setup files in"),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Preview files without creating them"
    ),
) -> None:
    """
    Generate production-ready configuration files (Docker Compose).
    Usage:
      meridian setup                # Create files in current directory
      meridian setup ./prod         # Create files in ./prod
      meridian setup --dry-run      # Preview what would be created
    """
    docker_compose = """
version: '3.8'

services:
  # 1. Postgres with pgvector (Offline Store + Context Store)
  postgres:
    image: pgvector/pgvector:pg16
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: meridian
    volumes:
      - meridian_postgres_data:/var/lib/postgresql/data

  # 2. Redis (Online Store + Cache)
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - meridian_redis_data:/data

volumes:
  meridian_postgres_data:
  meridian_redis_data:
"""
    env_example = """
# Meridian Production Config

# Security
MERIDIAN_API_KEY=change_me_to_something_secure

# Data Stores
MERIDIAN_REDIS_URL=redis://localhost:6379
MERIDIAN_POSTGRES_URL=postgresql://user:password@localhost:5432/meridian  # pragma: allowlist secret

# LLM Providers (Required for Context Store)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
COHERE_API_KEY=...
"""

    # File paths
    dc_path = os.path.join(dir, "docker-compose.yml")
    env_path = os.path.join(dir, ".env.production")

    if dry_run:
        # Dry run: show what would be created
        console.print(
            Panel(
                f"[bold]Dry Run:[/bold] Would create the following files:\n\n"
                f"  [cyan]{dc_path}[/cyan]\n"
                f"  [cyan]{env_path}[/cyan]\n\n"
                f"Run without --dry-run to create files.",
                title="Setup Preview",
                style="yellow",
            )
        )
        with console.pager():
            console.print("\n[bold]docker-compose.yml contents:[/bold]")
            console.print(docker_compose.strip())
            console.print("\n[bold].env.production contents:[/bold]")
            console.print(env_example.strip())
        return

    # Ensure directory exists
    if not os.path.exists(dir):
        os.makedirs(dir)
        console.print(f"Created directory: [bold cyan]{dir}[/bold cyan]")

    if os.path.exists(dc_path):
        console.print(f"[yellow]Warning:[/yellow] {dc_path} already exists. Skipping.")
    else:
        with open(dc_path, "w") as f:
            f.write(docker_compose.strip())
        console.print("Created [bold]docker-compose.yml[/bold]")

    if os.path.exists(env_path):
        console.print(f"[yellow]Warning:[/yellow] {env_path} already exists. Skipping.")
    else:
        # Systemic Fix: Use os.open to set permissions AT CREATION TIME
        fd = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, env_example.strip().encode("utf-8"))
        finally:
            os.close(fd)
        console.print("Created [bold].env.production[/bold]")

    console.print("\n[green]Setup Complete![/green]")
    console.print("To start infrastructure, run:")
    console.print("  [bold]docker compose up -d[/bold]")


@app.command(name="init")
def init(
    name: str = typer.Argument("meridian_project", help="Project name"),
    demo: bool = typer.Option(False, help="Include demo features and data"),
    interactive: bool = typer.Option(True, help="Run in interactive mode"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview file creation without writing"
    ),
) -> None:
    """
    Initialize a new Meridian project.
    """
    if os.path.exists(name) and not dry_run:
        console.print(f"[bold red]Error:[/bold red] Directory '{name}' already exists.")
        raise typer.Exit(1)

    if dry_run:
        console.print(f"[dim][Dry Run] Would create directory: {name}[/dim]")
    else:
        os.makedirs(name)
        console.print(f"Created directory: [bold cyan]{name}[/bold cyan]")

    # Interactive Configuration
    api_key_lines = []
    if interactive:
        # Check if we are in a TTY
        if sys.stdin.isatty():
            console.print("\n[bold]Configuration[/bold]")
            target_provider = typer.prompt(
                "Which LLM provider do you want to configure? (openai/anthropic/cohere/skip)",
                default="skip",
            ).lower()

            if target_provider == "openai":
                k = typer.prompt("Enter OpenAI API Key", hide_input=True)
                api_key_lines.append(f"OPENAI_API_KEY={k}")
            elif target_provider == "anthropic":
                k = typer.prompt("Enter Anthropic API Key", hide_input=True)
                api_key_lines.append(f"ANTHROPIC_API_KEY={k}")
            elif target_provider == "cohere":
                k = typer.prompt("Enter Cohere API Key", hide_input=True)
                api_key_lines.append(f"COHERE_API_KEY={k}")

    # Basic scaffold
    gitignore = """
__pycache__/
*.pyc
.env
.venv
*.db
    """
    if dry_run:
        console.print(f"[dim][Dry Run] Would create file: {name}/.gitignore[/dim]")
    else:
        with open(os.path.join(name, ".gitignore"), "w") as f:
            f.write(gitignore.strip())

    if api_key_lines:
        env_path = os.path.join(name, ".env")
        if dry_run:
            console.print(
                f"[dim][Dry Run] Would create file: {name}/.env (permissions 0600)[/dim]"
            )
            console.print(f"[dim][Dry Run] Content: keys={len(api_key_lines)}[/dim]")
        else:
            # Systemic Fix: Use os.open to set permissions AT CREATION TIME (avoids race condition)
            # 0o600 = Read/Write by owner only.
            fd = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                content = "\n".join(api_key_lines) + "\n"
                os.write(fd, content.encode("utf-8"))
            finally:
                os.close(fd)

            console.print(
                "Created [bold].env[/bold] with API key (permissions restricted to 0600)."
            )

    if demo:
        # Create features.py
        features_py = """
from meridian.core import FeatureStore, entity, feature
from meridian.context import context, Context, ContextItem
from meridian.retrieval import retriever
import random
import os

# Use default local stack (DuckDB + In-Memory)
store = FeatureStore()

@entity(store)
class User:
    user_id: str

# 1. Standard ML Feature
@feature(entity=User, refresh="5m", materialize=True)
def engagement_score(user_id: str) -> float:
    # Simulate a score
    return round(random.random() * 100, 2)

# 2. RAG / Context Store
# We assume there is an index called 'knowledge_base' (created via seed.py)

@retriever(index="knowledge_base", top_k=2)
async def semantic_search(query: str) -> list[str]:
    # In a real app with pgvector, this searches vectors.
    # For this local demo without Postgres/OpenAI keys, we mock the return
    # if the index isn't reachable or keys aren't set.
    return [
        "Meridian allows defining features in Python.",
        "The Context Store manages token budgets for LLMs."
    ]

@context(store, max_tokens=1000)
async def chatbot_context(user_id: str, query: str) -> list[ContextItem]:
    # Fetch data in parallel
    score = await store.get_feature("engagement_score", user_id)
    docs = await semantic_search(query)

    return [
        ContextItem(content=f"User Engagement: {score}", priority=2),
        ContextItem(content=str(docs), priority=1, required=True),
        ContextItem(content="System: You are a helpful assistant.", priority=0, required=True),
    ]
"""
        if dry_run:
            console.print(f"[dim][Dry Run] Would create file: {name}/features.py[/dim]")
        else:
            with open(os.path.join(name, "features.py"), "w") as f:
                f.write(features_py.strip())

        # Create README
        readme = """
# Meridian Demo Project

This is a generated demo project.

## Quickstart

1. **Install Meridian**:
   ```bash
   pip install "meridian-oss[ui]"
   ```

2. **Run the Server**:
   ```bash
   meridian serve features.py
   ```

3. **Query Context (E.g. for User 'u1')**:
   ```bash
   meridian context explain u1 --query "What is Meridian?"
   ```
"""
        if dry_run:
            console.print(f"[dim][Dry Run] Would create file: {name}/README.md[/dim]")
        else:
            with open(os.path.join(name, "README.md"), "w") as f:
                f.write(readme.strip())

        console.print(f"[green]Initialized demo project in '{name}'[/green]")
        console.print(
            "Run [bold]meridian serve features.py[/bold] inside the directory to start."
        )

    else:
        # Empty features.py
        if dry_run:
            console.print(
                f"[dim][Dry Run] Would create file: {name}/features.py (Empty)[/dim]"
            )
        else:
            with open(os.path.join(name, "features.py"), "w") as f:
                f.write(
                    "from meridian.core import FeatureStore\n\nstore = FeatureStore()\n"
                )
        console.print(f"[green]Initialized empty project in '{name}'[/green]")


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
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
) -> None:
    """
    Starts the Meridian server with a live TUI dashboard.

    Example:
        meridian serve features.py
        meridian serve features.py --port 9000 --verbose
    """
    import logging

    if verbose:
        logging.basicConfig(level=logging.DEBUG)
        console.print("[dim]Verbose mode enabled[/dim]")
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

        # === Startup Checks (UX) ===
        # Check 1: RAG Usage without Keys
        has_retrievers = len(store.retriever_registry.retrievers) > 0
        has_openai = os.getenv("OPENAI_API_KEY") is not None
        has_cohere = os.getenv("COHERE_API_KEY") is not None

        if has_retrievers and not (has_openai or has_cohere):
            console.print(
                Panel(
                    "[yellow]Warning: Retrievers detected but no LLM API Key found.[/yellow]\n"
                    "Vector search and generation will fail.\n"
                    "Fix: set [bold]OPENAI_API_KEY[/bold] or [bold]COHERE_API_KEY[/bold] in .env",
                    title="Configuration Warning",
                    border_style="yellow",
                )
            )

        # Start scheduler
        store.start()

        # Set API key in env for the server to pick up
        if api_key:
            os.environ["MERIDIAN_API_KEY"] = api_key

        app = create_app(store)

        # Create Rich Layout
        layout = Layout()
        layout.split(
            Layout(name="header", size=10),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3),
        )

        ascii_banner = """
███╗   ███╗███████╗██████╗ ██╗██████╗ ██╗ █████╗ ███╗   ██╗
████╗ ████║██╔════╝██╔══██╗██║██╔══██╗██║██╔══██╗████╗  ██║
██╔████╔██║█████╗  ██████╔╝██║██║  ██║██║███████║██╔██╗ ██║
██║╚██╔╝██║██╔══╝  ██╔══██╗██║██║  ██║██║██╔══██║██║╚██╗██║
██║ ╚═╝ ██║███████╗██║  ██║██║██████╔╝██║██║  ██║██║ ╚████║
╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚═╝╚═════╝ ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝
"""
        layout["header"].update(
            Panel(
                f"[bold blue]{ascii_banner}[/bold blue]\n[center]Feature Store & Context Engine | Serving [bold cyan]{file}[/bold cyan][/center]",
                style="white",
                border_style="blue",
            )
        )

        def generate_metrics_table() -> Panel:
            table = Table(title="📊 Dashboard", expand=True, show_header=False)
            table.add_column("Metric", style="cyan", width=20)
            table.add_column("Value", style="white")

            # Status section
            table.add_row("Status", "[bold green]● Running[/bold green]")
            table.add_row("Started", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            table.add_row("Environment", os.getenv("MERIDIAN_ENV", "development"))

            table.add_section()

            # Registry counts
            num_entities = len(store.registry.entities)
            num_features = len(store.registry.features)
            num_retrievers = len(store.retriever_registry.retrievers)
            ctx_len = len(
                [
                    f
                    for f in store.registry.features.values()
                    if getattr(f, "is_context", False)
                ]
            )

            table.add_row("📦 Entities", f"[bold]{num_entities}[/bold]")
            table.add_row("⚡ Features", f"[bold]{num_features}[/bold]")
            table.add_row("🔍 Retrievers", f"[bold]{num_retrievers}[/bold]")
            table.add_row("📝 Contexts", f"[bold]{ctx_len}[/bold]")

            table.add_section()

            # Endpoints section
            table.add_row("[dim]API Endpoints:[/dim]", "")
            table.add_row(
                "  Health",
                f"[link=http://{host}:{port}/health]http://{host}:{port}/health[/link]",
            )
            table.add_row(
                "  Docs",
                f"[link=http://{host}:{port}/docs]http://{host}:{port}/docs[/link]",
            )
            table.add_row(
                "  Metrics",
                f"[link=http://{host}:{port}/metrics]http://{host}:{port}/metrics[/link]",
            )

            table.add_section()

            # Quick test commands
            table.add_row("[dim]Quick Test:[/dim]", "")
            table.add_row("", f"[dim]curl http://{host}:{port}/health[/dim]")

            # Find a feature to demo
            if num_features > 0:
                demo_feature = next(iter(store.registry.features.keys()))
                table.add_row(
                    "",
                    f'[dim]curl -X POST http://{host}:{port}/features -d \'{{"entity_id": "u1", "features": ["{demo_feature}"]}}\' -H \'Content-Type: application/json\'[/dim]',
                )

            return Panel(
                table, title="[bold blue]System Status[/bold blue]", border_style="blue"
            )

        layout["main"].update(generate_metrics_table())

        layout["footer"].update(
            Panel(
                f"Dashboard available at: [bold underline]http://{host}:{port}/dashboard[/bold underline] | Press [bold red]Ctrl+C[/bold red] to stop",
                style="dim",
            )
        )

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
    port: int = typer.Option(8501, help="Port to run the UI on"),
    api_port: int = typer.Option(8502, help="Port for API backend"),
) -> None:
    """
    Launches the Meridian UI.

    Starts a Next.js-based UI with a FastAPI backend for exploring
    your Feature Store and Context definitions.

    Example:
        meridian ui features.py
        meridian ui features.py --port 3000
    """
    if not os.path.exists(file):
        console.print(f"[bold red]Error:[/bold red] File '{file}' not found.")
        raise typer.Exit(code=1)

    # Next.js UI with FastAPI backend
    import subprocess  # nosec B404
    import threading
    import time
    import webbrowser

    from .ui_server import run_server

    console.print(
        Panel(
            f"Starting Meridian UI\n\n"
            f"  API Backend: http://127.0.0.1:{api_port}\n"
            f"  UI Frontend: http://localhost:{port}\n\n"
            f"Loading: [bold cyan]{file}[/bold cyan]",
            title="Meridian UI",
            style="bold blue",
        )
    )

    # Check if Next.js build exists
    ui_next_dir = os.path.join(os.path.dirname(__file__), "ui-next")
    if not os.path.exists(os.path.join(ui_next_dir, "node_modules")):
        console.print(
            "[yellow]Warning:[/yellow] Next.js dependencies not installed.\n"
            "Run the following to set up:\n"
            f"  cd {ui_next_dir} && npm install\n\n"
            "Falling back to API-only mode..."
        )
        # Just run the API server
        run_server(file, port=api_port, host="127.0.0.1")
        return

    # Start API server in background thread
    def start_api() -> None:
        import uvicorn
        from .ui_server import load_module, app as api_app

        load_module(file)
        uvicorn.run(api_app, host="127.0.0.1", port=api_port, log_level="warning")

    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    # Wait for API to be ready
    time.sleep(1)

    # Start Next.js dev server
    console.print("[green]Starting UI server...[/green]")
    try:
        # Open browser after a short delay
        def open_browser() -> None:
            time.sleep(3)
            webbrowser.open(f"http://localhost:{port}")

        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()

        # Run Next.js dev server
        subprocess.run(  # nosec B603 B607
            ["npm", "run", "dev", "--", "-p", str(port)],
            cwd=ui_next_dir,
            check=True,
        )
    except FileNotFoundError:
        console.print(
            "[bold red]Error:[/bold red] npm not found. "
            "Please install Node.js to use the UI."
        )
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print("\nUI stopped.")


@app.command(name="doctor")
def doctor() -> None:
    """
    Diagnose configuration and connectivity issues.
    """
    from .doctor import run_doctor

    run_doctor()


context_app = typer.Typer(help="Manage and inspect Context Store assemblies.")
app.add_typer(context_app, name="context")


@context_app.command(name="show")
def context_show_cmd(
    context_id: str = typer.Argument(..., help="The Context ID to retrieve"),
    host: str = typer.Option("127.0.0.1", help="Meridian server host"),
    port: int = typer.Option(8000, help="Meridian server port"),
    lineage: bool = typer.Option(
        False, "--lineage", "-l", help="Show only lineage info"
    ),
) -> None:
    """
    Retrieve and display a historical context by ID.

    Example:
      meridian context show 01912345-6789-7abc-def0-123456789abc
      meridian context show <context_id> --lineage
    """
    import urllib.request
    import urllib.error
    import json

    endpoint = "lineage" if lineage else ""
    url = f"http://{host}:{port}/v1/context/{context_id}" + (
        f"/{endpoint}" if endpoint else ""
    )
    console.print(f"Fetching context [bold cyan]{context_id}[/bold cyan] from {url}...")

    if not url.lower().startswith(("http://", "https://")):
        console.print("[bold red]Error:[/bold red] Invalid URL scheme")
        raise typer.Exit(1)

    try:
        req = urllib.request.Request(url)
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
            if lineage:
                title = f"Lineage: {context_id}"
            else:
                title = f"Context: {context_id}"

            console.print(
                Panel(
                    json.dumps(data, indent=2, default=str),
                    title=title,
                    border_style="green",
                )
            )

    except urllib.error.HTTPError as e:
        if e.code == 404:
            console.print(
                f"[bold red]Not Found:[/bold red] Context '{context_id}' does not exist."
            )
        else:
            console.print(f"[bold red]Error:[/bold red] HTTP {e.code}: {e.reason}")
        raise typer.Exit(1)
    except urllib.error.URLError as e:
        console.print(
            f"[bold red]Connection Failed:[/bold red] {e}. Run [bold]meridian doctor[/bold] to check connectivity."
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@context_app.command(name="list")
def context_list_cmd(
    host: str = typer.Option("127.0.0.1", help="Meridian server host"),
    port: int = typer.Option(8000, help="Meridian server port"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of contexts to list"),
    start: str = typer.Option(None, "--start", "-s", help="Start time (ISO format)"),
    end: str = typer.Option(None, "--end", "-e", help="End time (ISO format)"),
) -> None:
    """
    List recent contexts for debugging/audit.

    Example:
      meridian context list --limit 10
      meridian context list --start 2024-01-01T00:00:00Z --end 2024-01-02T00:00:00Z
    """
    import urllib.request
    import urllib.error
    import json
    from urllib.parse import urlencode
    from typing import Dict, Union

    params: Dict[str, Union[int, str]] = {"limit": limit}
    if start:
        params["start"] = start
    if end:
        params["end"] = end

    url = f"http://{host}:{port}/v1/contexts?{urlencode(params)}"
    console.print(f"Fetching contexts from {url}...")

    if not url.lower().startswith(("http://", "https://")):
        console.print("[bold red]Error:[/bold red] Invalid URL scheme")
        raise typer.Exit(1)

    try:
        req = urllib.request.Request(url)
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

            # Display as a table
            table = Table(title=f"Contexts (limit={limit})", expand=True)
            table.add_column("Context ID", style="cyan", no_wrap=True)
            table.add_column("Timestamp", style="green")
            table.add_column("Version", style="dim")
            table.add_column("Content Preview", style="white", max_width=40)

            contexts = data.get("contexts", [])
            for ctx in contexts:
                content_preview = (
                    ctx.get("content", "")[:40] + "..."
                    if len(ctx.get("content", "")) > 40
                    else ctx.get("content", "")
                )
                table.add_row(
                    ctx.get("context_id", ""),
                    ctx.get("timestamp", ""),
                    ctx.get("version", ""),
                    content_preview,
                )

            console.print(table)
            console.print(f"\n[dim]Total: {len(contexts)} contexts[/dim]")

    except urllib.error.URLError as e:
        console.print(
            f"[bold red]Connection Failed:[/bold red] {e}. Run [bold]meridian doctor[/bold] to check connectivity."
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@context_app.command(name="export")
def context_export_cmd(
    context_id: str = typer.Argument(..., help="The Context ID to export"),
    host: str = typer.Option("127.0.0.1", help="Meridian server host"),
    port: int = typer.Option(8000, help="Meridian server port"),
    format: str = typer.Option(
        "json", "--format", "-f", help="Export format: json, yaml"
    ),
    output: str = typer.Option(
        None, "--output", "-o", help="Output file (default: stdout)"
    ),
) -> None:
    """
    Export a context for audit/debugging.

    Example:
      meridian context export <context_id> --format json
      meridian context export <context_id> --output context.json
      meridian context export <context_id> --format yaml -o context.yaml
    """
    import urllib.request
    import urllib.error
    import json

    url = f"http://{host}:{port}/v1/context/{context_id}"
    console.print(f"Exporting context [bold cyan]{context_id}[/bold cyan]...")

    if not url.lower().startswith(("http://", "https://")):
        console.print("[bold red]Error:[/bold red] Invalid URL scheme")
        raise typer.Exit(1)

    try:
        req = urllib.request.Request(url)
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

            # Format output
            if format == "yaml":
                try:
                    import yaml  # type: ignore[import-untyped]

                    formatted = yaml.dump(
                        data, default_flow_style=False, allow_unicode=True
                    )
                except ImportError:
                    console.print(
                        "[yellow]Warning:[/yellow] PyYAML not installed. Falling back to JSON."
                    )
                    formatted = json.dumps(data, indent=2, default=str)
            else:
                formatted = json.dumps(data, indent=2, default=str)

            # Output to file or stdout
            if output:
                with open(output, "w") as f:
                    f.write(formatted)
                console.print(f"[green]Exported to {output}[/green]")
            else:
                console.print(formatted)

    except urllib.error.HTTPError as e:
        if e.code == 404:
            console.print(
                f"[bold red]Not Found:[/bold red] Context '{context_id}' does not exist."
            )
        else:
            console.print(f"[bold red]Error:[/bold red] HTTP {e.code}: {e.reason}")
        raise typer.Exit(1)
    except urllib.error.URLError as e:
        console.print(
            f"[bold red]Connection Failed:[/bold red] {e}. Run [bold]meridian doctor[/bold] to check connectivity."
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@context_app.command(name="explain")
def explain_cmd(
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
            f"[bold red]Connection Failed:[/bold red] {e}. Run [bold]meridian doctor[/bold] to check connectivity."
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
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Preview changes without executing"
    ),
) -> None:
    """
    Manage vector indexes.
    Usage:
      meridian index create my_index --dimension=1536
      meridian index status my_index
      meridian index create my_index --dry-run  # Preview only
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
                table_name = f"meridian_index_{name}"
                if dry_run:
                    console.print(
                        Panel(
                            f"[bold]Dry Run:[/bold] Would create index table\n\n"
                            f"  Table:     [cyan]{table_name}[/cyan]\n"
                            f"  Dimension: [cyan]{dimension}[/cyan]\n"
                            f"  Database:  [dim]{url.split('@')[-1] if '@' in url else url}[/dim]\n\n"
                            f"Run without --dry-run to execute.",
                            title="Index Preview",
                            style="yellow",
                        )
                    )
                    return

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


@app.command(name="deploy")
def deploy_cmd(
    target: str = typer.Argument(
        "fly", help="Deployment target: fly, cloudrun, ecs, render, railway"
    ),
    file: str = typer.Option(
        "features.py", "--file", "-f", help="Feature definition file"
    ),
    app_name: str = typer.Option(
        "meridian-app", "--name", "-n", help="Application name"
    ),
    region: str = typer.Option("iad", "--region", "-r", help="Deployment region"),
    output: str = typer.Option(".", "--output", "-o", help="Output directory"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview generated files without writing"
    ),
) -> None:
    """
    Generate deployment configuration for cloud platforms.

    Usage:
      meridian deploy fly --name my-app          # Generate fly.toml
      meridian deploy cloudrun --name my-app     # Generate Cloud Run config
      meridian deploy ecs --name my-app          # Generate ECS task definition
      meridian deploy --dry-run                  # Preview without writing
    """
    # Common Dockerfile for all deployments
    dockerfile = f"""# Auto-generated by Meridian CLI
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY {file} .
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s \\
  CMD curl -f http://localhost:8000/health || exit 1

# Run server
CMD ["meridian", "serve", "{file}", "--host", "0.0.0.0", "--port", "8000"]
"""

    requirements_txt = """meridian>=1.2.0
redis>=4.0.0
asyncpg>=0.27.0
"""

    configs: dict[str, dict[str, str]] = {
        "fly": {
            "fly.toml": f"""# Auto-generated by Meridian CLI
app = "{app_name}"
primary_region = "{region}"

[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "8000"
  MERIDIAN_ENV = "production"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1

[[services]]
  internal_port = 8000
  protocol = "tcp"

  [[services.ports]]
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

  [[services.http_checks]]
    interval = "10s"
    timeout = "2s"
    path = "/health"
""",
        },
        "cloudrun": {
            "service.yaml": f"""# Auto-generated by Meridian CLI
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: {app_name}
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "1"
        autoscaling.knative.dev/maxScale: "10"
    spec:
      containers:
        - image: gcr.io/PROJECT_ID/{app_name}:latest
          ports:
            - containerPort: 8000
          env:
            - name: MERIDIAN_ENV
              value: production
          resources:
            limits:
              cpu: "1"
              memory: 512Mi
          startupProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
""",
            "cloudbuild.yaml": f"""# Auto-generated by Meridian CLI
steps:
  - name: gcr.io/cloud-builders/docker
    args: ["build", "-t", "gcr.io/$PROJECT_ID/{app_name}:$COMMIT_SHA", "."]
  - name: gcr.io/cloud-builders/docker
    args: ["push", "gcr.io/$PROJECT_ID/{app_name}:$COMMIT_SHA"]
  - name: gcr.io/google.com/cloudsdktool/cloud-sdk
    entrypoint: gcloud
    args:
      - run
      - deploy
      - {app_name}
      - --image=gcr.io/$PROJECT_ID/{app_name}:$COMMIT_SHA
      - --region={region}
      - --platform=managed
images:
  - gcr.io/$PROJECT_ID/{app_name}:$COMMIT_SHA
""",
        },
        "ecs": {
            "task-definition.json": f"""{{
  "family": "{app_name}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::ACCOUNT_ID:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {{
      "name": "{app_name}",
      "image": "ACCOUNT_ID.dkr.ecr.{region}.amazonaws.com/{app_name}:latest",
      "essential": true,
      "portMappings": [
        {{
          "containerPort": 8000,
          "protocol": "tcp"
        }}
      ],
      "environment": [
        {{"name": "MERIDIAN_ENV", "value": "production"}}
      ],
      "healthCheck": {{
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }},
      "logConfiguration": {{
        "logDriver": "awslogs",
        "options": {{
          "awslogs-group": "/ecs/{app_name}",
          "awslogs-region": "{region}",
          "awslogs-stream-prefix": "ecs"
        }}
      }}
    }}
  ]
}}
""",
        },
        "render": {
            "render.yaml": f"""# Auto-generated by Meridian CLI
services:
  - type: web
    name: {app_name}
    env: docker
    region: {region}
    plan: starter
    healthCheckPath: /health
    envVars:
      - key: MERIDIAN_ENV
        value: production
      - key: PORT
        value: 8000
""",
        },
        "railway": {
            "railway.json": f"""{{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {{
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  }},
  "deploy": {{
    "startCommand": "meridian serve {file} --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 30,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }}
}}
""",
        },
    }

    if target not in configs:
        console.print(
            f"[bold red]Unknown target:[/bold red] {target}\n"
            f"Available targets: {', '.join(configs.keys())}"
        )
        raise typer.Exit(1)

    # Get target-specific files
    target_files = configs[target]

    # Add common files
    all_files = {
        "Dockerfile": dockerfile,
        "requirements.txt": requirements_txt,
        **target_files,
    }

    if dry_run:
        console.print(
            Panel(
                f"[bold]Dry Run:[/bold] Would create {len(all_files)} files for {target}\n\n"
                + "\n".join(f"  [cyan]{f}[/cyan]" for f in all_files.keys())
                + "\n\nRun without --dry-run to create files.",
                title=f"Deploy to {target.title()}",
                style="yellow",
            )
        )
        # Show a preview of each file
        for filename, content in all_files.items():
            console.print(f"\n[bold]{filename}:[/bold]")
            console.print(
                Panel(content.strip()[:500] + ("..." if len(content) > 500 else ""))
            )
        return

    # Create output directory if needed
    if not os.path.exists(output):
        os.makedirs(output)
        console.print(f"Created directory: [bold cyan]{output}[/bold cyan]")

    # Write files
    created_files = []
    for filename, content in all_files.items():
        filepath = os.path.join(output, filename)
        if os.path.exists(filepath):
            console.print(f"[yellow]Warning:[/yellow] {filepath} exists. Skipping.")
        else:
            with open(filepath, "w") as f:
                f.write(content.strip())
            created_files.append(filename)
            console.print(f"Created [bold]{filename}[/bold]")

    # Show next steps
    console.print("\n[green]Deployment files generated![/green]\n")

    next_steps = {
        "fly": [
            "fly auth login",
            "fly launch --no-deploy",
            "fly secrets set MERIDIAN_REDIS_URL=... MERIDIAN_POSTGRES_URL=...",
            "fly deploy",
        ],
        "cloudrun": [
            "gcloud auth login",
            "gcloud config set project YOUR_PROJECT",
            "gcloud builds submit",
        ],
        "ecs": [
            "aws ecr create-repository --repository-name " + app_name,
            "docker build -t " + app_name + " .",
            "docker push ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/" + app_name,
            "aws ecs register-task-definition --cli-input-json file://task-definition.json",
        ],
        "render": [
            "Connect your GitHub repo to Render",
            "Render will auto-deploy on push",
        ],
        "railway": [
            "railway login",
            "railway init",
            "railway up",
        ],
    }

    console.print("[bold]Next steps:[/bold]")
    for i, step in enumerate(next_steps.get(target, []), 1):
        console.print(f"  {i}. [dim]{step}[/dim]")


if __name__ == "__main__":
    app()
