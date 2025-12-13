import typer
import uvicorn
import os
import sys
import importlib.util
from typing import Any
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
    stream: str = typer.Option("fabra_events", help="Stream key to listen to"),
    count: int = typer.Option(10, help="Number of events to fetch per poll"),
    redis_url: str = typer.Option(
        None, envvar="FABRA_REDIS_URL", help="Redis URL Override"
    ),
) -> None:
    """
    Manage or listen to Fabra events.
    Usage: fabra events listen --stream=my_stream
    """
    if action != "listen":
        console.print(f"[bold red]Unknown action:[/bold red] {action}")
        raise typer.Exit(1)

    import asyncio
    from redis.asyncio import Redis

    url = redis_url or os.getenv("FABRA_REDIS_URL") or "redis://localhost:6379"

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
    Fabra CLI
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
        None, envvar="FABRA_REDIS_URL", help="Redis URL Override"
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
      fabra setup                # Create files in current directory
      fabra setup ./prod         # Create files in ./prod
      fabra setup --dry-run      # Preview what would be created
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
      POSTGRES_DB: fabra
    volumes:
      - fabra_postgres_data:/var/lib/postgresql/data

  # 2. Redis (Online Store + Cache)
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - fabra_redis_data:/data

volumes:
  fabra_postgres_data:
  fabra_redis_data:
"""
    env_example = """
# Fabra Production Config

# Security
FABRA_API_KEY=change_me_to_something_secure

# Data Stores
FABRA_REDIS_URL=redis://localhost:6379
FABRA_POSTGRES_URL=postgresql://user:password@localhost:5432/fabra  # pragma: allowlist secret

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
    name: str = typer.Argument("fabra_project", help="Project name"),
    demo: bool = typer.Option(False, help="Include demo features and data"),
    interactive: bool = typer.Option(True, help="Run in interactive mode"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview file creation without writing"
    ),
) -> None:
    """
    Initialize a new Fabra project.
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
from fabra.core import FeatureStore, entity, feature
from fabra.context import context, Context, ContextItem
from fabra.retrieval import retriever
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
        "Fabra allows defining features in Python.",
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
# Fabra Demo Project

This is a generated demo project.

## Quickstart

1. **Install Fabra**:
   ```bash
   pip install "fabra[ui]"
   ```

2. **Run the Server**:
   ```bash
   fabra serve features.py
   ```

3. **Query Context (E.g. for User 'u1')**:
   ```bash
   fabra context explain u1 --query "What is Fabra?"
   ```
"""
        if dry_run:
            console.print(f"[dim][Dry Run] Would create file: {name}/README.md[/dim]")
        else:
            with open(os.path.join(name, "README.md"), "w") as f:
                f.write(readme.strip())

        console.print(f"[green]Initialized demo project in '{name}'[/green]")
        console.print(
            "Run [bold]fabra serve features.py[/bold] inside the directory to start."
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
                    "from fabra.core import FeatureStore\n\nstore = FeatureStore()\n"
                )
        console.print(f"[green]Initialized empty project in '{name}'[/green]")


@app.command(name="version")
def version_cmd() -> None:
    """
    Prints the Fabra version.
    """
    from fabra import __version__

    console.print(f"Fabra v{__version__}")


@app.command(name="serve")
def serve(
    file: str = typer.Argument(
        ..., help="Path to the feature definition file (e.g., features.py)"
    ),
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
    api_key: str = typer.Option(
        None, envvar="FABRA_API_KEY", help="API Key for security"
    ),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
) -> None:
    """
    Starts the Fabra server with a live TUI dashboard.

    Example:
        fabra serve features.py
        fabra serve features.py --port 9000 --verbose
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
            f"Starting Fabra on http://{host}:{port}",
            title="Fabra",
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
            os.environ["FABRA_API_KEY"] = api_key

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
            table.add_row("Environment", os.getenv("FABRA_ENV", "development"))

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

            # Quick test commands - simpler and more prominent
            table.add_row("[bold cyan]Try This:[/bold cyan]", "")

            # Find a feature to demo with simpler GET endpoint
            if num_features > 0:
                demo_feature = next(iter(store.registry.features.keys()))
                simple_curl = f"curl http://{host}:{port}/features/{demo_feature}?entity_id=user_123"
                table.add_row("", f"[cyan]{simple_curl}[/cyan]")
                table.add_row(
                    "[dim]Expected:[/dim]",
                    '[dim]{"value": ..., "freshness_ms": 0}[/dim]',
                )
            else:
                table.add_row("", f"[dim]curl http://{host}:{port}/health[/dim]")

            # Show context endpoint if contexts exist
            if ctx_len > 0:
                table.add_row("", "")
                table.add_row("[dim]Or try context:[/dim]", "")
                ctx_name = next(
                    (
                        f.name
                        for f in store.registry.features.values()
                        if getattr(f, "is_context", False)
                    ),
                    "chat_context",
                )
                table.add_row(
                    "",
                    f'[dim]curl -X POST http://{host}:{port}/v1/context/{ctx_name} -d \'{{"user_id":"u1"}}\' -H "Content-Type: application/json"[/dim]',
                )

            table.add_section()

            # Links
            table.add_row("[dim]Learn More:[/dim]", "")
            table.add_row(
                "  Playground",
                "[link=https://fabraoss.vercel.app]https://fabraoss.vercel.app[/link]",
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
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Don't auto-open browser"
    ),
) -> None:
    """
    Launches the Fabra UI.

    Starts a Next.js-based UI with a FastAPI backend for exploring
    your Feature Store and Context definitions.

    Example:
        fabra ui features.py
        fabra ui features.py --port 3000
    """
    if not os.path.exists(file):
        console.print(f"[bold red]Error:[/bold red] File '{file}' not found.")
        raise typer.Exit(code=1)

    # Validate FeatureStore exists before starting servers
    sys.path.append(os.getcwd())
    try:
        module_name = os.path.splitext(os.path.basename(file))[0]
        spec = importlib.util.spec_from_file_location(module_name, file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec for {file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        store = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, FeatureStore):
                store = attr
                break

        if not store:
            console.print(
                "[bold red]Error:[/bold red] No FeatureStore instance found "
                "in the provided file."
            )
            raise typer.Exit(code=1)
    except Exception as e:
        if "No FeatureStore" in str(e):
            raise
        console.print(f"[bold red]Error:[/bold red] Failed to load module: {e}")
        raise typer.Exit(code=1)

    # Next.js UI with FastAPI backend
    import subprocess  # nosec B404
    import threading
    import time
    import webbrowser

    from .ui_server import run_server

    console.print(
        Panel(
            f"Starting Fabra UI\n\n"
            f"  API Backend: http://127.0.0.1:{api_port}\n"
            f"  UI Frontend: http://localhost:{port}\n\n"
            f"Loading: [bold cyan]{file}[/bold cyan]",
            title="Fabra UI",
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
        # Open browser after a short delay (unless --no-browser)
        if not no_browser:

            def open_browser() -> None:
                time.sleep(3)
                webbrowser.open(f"http://localhost:{port}")

            browser_thread = threading.Thread(target=open_browser, daemon=True)
            browser_thread.start()
            console.print(f"[dim]Opening http://localhost:{port} in browser...[/dim]")

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


context_app = typer.Typer(help="Manage and inspect Context Store assemblies.")
app.add_typer(context_app, name="context")


@context_app.command(name="show")
def context_show_cmd(
    context_id: str = typer.Argument(..., help="The Context ID to retrieve"),
    host: str = typer.Option("127.0.0.1", help="Fabra server host"),
    port: int = typer.Option(8000, help="Fabra server port"),
    lineage: bool = typer.Option(
        False, "--lineage", "-l", help="Show only lineage info"
    ),
) -> None:
    """
    Retrieve and display a historical context by ID.

    Example:
      fabra context show 01912345-6789-7abc-def0-123456789abc
      fabra context show <context_id> --lineage
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
        api_key = os.getenv("FABRA_API_KEY")
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
            f"[bold red]Connection Failed:[/bold red] {e}. Run [bold]fabra doctor[/bold] to check connectivity."
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@context_app.command(name="list")
def context_list_cmd(
    host: str = typer.Option("127.0.0.1", help="Fabra server host"),
    port: int = typer.Option(8000, help="Fabra server port"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of contexts to list"),
    start: str = typer.Option(None, "--start", "-s", help="Start time (ISO format)"),
    end: str = typer.Option(None, "--end", "-e", help="End time (ISO format)"),
) -> None:
    """
    List recent contexts for debugging/audit.

    Example:
      fabra context list --limit 10
      fabra context list --start 2024-01-01T00:00:00Z --end 2024-01-02T00:00:00Z
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
        api_key = os.getenv("FABRA_API_KEY")
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
            table.add_column("Name", style="magenta")
            table.add_column("Timestamp", style="green")
            table.add_column("Tokens", style="yellow")
            table.add_column("Freshness", style="dim")

            # API returns a list directly, not a dict with "contexts" key
            contexts = data if isinstance(data, list) else data.get("contexts", [])
            for ctx in contexts:
                table.add_row(
                    ctx.get("context_id", ""),
                    ctx.get("name", ""),
                    ctx.get("timestamp", ""),
                    str(ctx.get("token_usage", "")),
                    ctx.get("freshness_status", ""),
                )

            console.print(table)
            console.print(f"\n[dim]Total: {len(contexts)} contexts[/dim]")

    except urllib.error.URLError as e:
        console.print(
            f"[bold red]Connection Failed:[/bold red] {e}. Run [bold]fabra doctor[/bold] to check connectivity."
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@context_app.command(name="export")
def context_export_cmd(
    context_id: str = typer.Argument(..., help="The Context ID to export"),
    host: str = typer.Option("127.0.0.1", help="Fabra server host"),
    port: int = typer.Option(8000, help="Fabra server port"),
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
      fabra context export <context_id> --format json
      fabra context export <context_id> --output context.json
      fabra context export <context_id> --format yaml -o context.yaml
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
        api_key = os.getenv("FABRA_API_KEY")
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
            f"[bold red]Connection Failed:[/bold red] {e}. Run [bold]fabra doctor[/bold] to check connectivity."
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@context_app.command(name="replay")
def context_replay_cmd(
    context_id: str = typer.Argument(..., help="Context ID to replay"),
    output: str = typer.Option(
        "pretty", "--output", "-o", help="Output format: json, pretty, html"
    ),
    host: str = typer.Option("127.0.0.1", help="Fabra server host"),
    port: int = typer.Option(8000, help="Fabra server port"),
) -> None:
    """
    Replay a historical context assembly.

    This command retrieves a stored context and displays it in various formats,
    allowing you to inspect exactly what data was used in a past LLM call.

    Examples:
      fabra context replay ctx_018f1234-5678-7abc-def0-123456789abc
      fabra context replay <context_id> --output json
      fabra context replay <context_id> --output html  # Opens in browser
    """
    import urllib.request
    import urllib.error
    import json
    import webbrowser

    # Fetch the context
    url = f"http://{host}:{port}/v1/context/{context_id}"

    if not url.lower().startswith(("http://", "https://")):
        console.print("[bold red]Error:[/bold red] Invalid URL scheme")
        raise typer.Exit(1)

    try:
        req = urllib.request.Request(url)
        api_key = os.getenv("FABRA_API_KEY")
        if api_key:
            req.add_header("X-API-Key", api_key)

        console.print(f"Replaying context [bold cyan]{context_id}[/bold cyan]...\n")

        with urllib.request.urlopen(req) as response:  # nosec B310
            if response.status != 200:
                console.print(
                    f"[bold red]Error:[/bold red] Server returned {response.status}"
                )
                raise typer.Exit(1)

            data = json.loads(response.read().decode())

            if output == "json":
                # Raw JSON output
                console.print(json.dumps(data, indent=2, default=str))

            elif output == "html":
                # Open visualization in browser
                viz_url = f"http://{host}:{port}/v1/context/{context_id}/visualize"
                console.print(f"Opening visualization in browser: {viz_url}")
                webbrowser.open(viz_url)

            else:  # pretty (default)
                # Rich formatted output
                ctx_id_short = data.get("context_id", context_id)[:12]
                meta = data.get("meta", {})
                lineage = data.get("lineage", {})
                content = data.get("content", "")

                # Header with status
                freshness = meta.get("freshness_status", "unknown")
                status_color = "green" if freshness == "guaranteed" else "yellow"
                status_icon = "✓" if freshness == "guaranteed" else "⚠"

                console.print(
                    Panel(
                        f"[bold]Context ID:[/bold] {ctx_id_short}...\n"
                        f"[bold]Timestamp:[/bold] {meta.get('timestamp', 'N/A')}\n"
                        f"[bold]Status:[/bold] [{status_color}]{status_icon} {freshness.upper()}[/{status_color}]",
                        title="[bold blue]Context Replay[/bold blue]",
                        border_style="blue",
                    )
                )

                # Token usage
                token_usage = meta.get("token_usage", 0)
                max_tokens = meta.get("max_tokens")
                if max_tokens:
                    pct = (token_usage / max_tokens) * 100
                    bar_width = 30
                    filled = int(bar_width * pct / 100)
                    bar = "█" * filled + "░" * (bar_width - filled)
                    console.print(
                        f"\n[bold]Token Budget:[/bold] [{bar}] {token_usage:,}/{max_tokens:,} ({pct:.1f}%)"
                    )

                # Lineage summary
                if lineage:
                    features_used = lineage.get("features_used", [])
                    retrievers_used = lineage.get("retrievers_used", [])
                    items_dropped = lineage.get("items_dropped", 0)

                    console.print("\n[bold]Lineage:[/bold]")
                    console.print(f"  Features:   {len(features_used)}")
                    console.print(f"  Retrievers: {len(retrievers_used)}")
                    console.print(f"  Dropped:    {items_dropped} items")

                    # Show features
                    if features_used:
                        console.print("\n[dim]Features Used:[/dim]")
                        for f in features_used[:5]:  # Limit display
                            name = f.get("feature_name", "unknown")
                            value = f.get("value", "N/A")
                            age_ms = f.get("freshness_ms", 0)
                            source = f.get("source", "compute")
                            console.print(
                                f"  • {name}: {value} [dim]({source}, {age_ms}ms old)[/dim]"
                            )
                        if len(features_used) > 5:
                            console.print(
                                f"  [dim]... and {len(features_used) - 5} more[/dim]"
                            )

                    # Show retrievers
                    if retrievers_used:
                        console.print("\n[dim]Retrievers Used:[/dim]")
                        for r in retrievers_used[:3]:
                            name = r.get("retriever_name", "unknown")
                            query = r.get("query", "")[:30]
                            count = r.get("results_count", 0)
                            latency = r.get("latency_ms", 0)
                            console.print(
                                f'  • {name}: "{query}..." → {count} results [dim]({latency:.1f}ms)[/dim]'
                            )

                # Content preview
                content_preview = (
                    content[:500] + "..." if len(content) > 500 else content
                )
                console.print(
                    Panel(
                        content_preview,
                        title="[bold]Content Preview[/bold]",
                        border_style="dim",
                    )
                )

                # Cost
                cost = meta.get("cost_usd", 0)
                if cost:
                    console.print(f"\n[dim]Estimated Cost: ${cost:.6f}[/dim]")

                # Tip
                console.print(
                    "\n[dim]Tip: Use --output json for full data, --output html for visualization[/dim]"
                )

    except urllib.error.HTTPError as e:
        if e.code == 404:
            console.print(
                f"[bold red]Not Found:[/bold red] Context '{context_id}' does not exist.\n"
                f"[dim]Contexts are stored for 24 hours by default.[/dim]"
            )
        else:
            console.print(f"[bold red]Error:[/bold red] HTTP {e.code}: {e.reason}")
        raise typer.Exit(1)
    except urllib.error.URLError as e:
        console.print(
            f"[bold red]Connection Failed:[/bold red] {e}\n"
            f"[dim]Make sure the Fabra server is running: fabra serve <file>[/dim]"
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@context_app.command(name="verify")
def context_verify_cmd(
    context_id: str = typer.Argument(..., help="The Context ID to verify"),
    host: str = typer.Option("127.0.0.1", help="Fabra server host"),
    port: int = typer.Option(8000, help="Fabra server port"),
) -> None:
    """
    Verify the cryptographic integrity of a context record.

    Checks that the record_hash and content_hash match the actual content,
    ensuring the context has not been tampered with.

    Example:
      fabra context verify ctx_018f3a2b-...
    """
    import urllib.request
    import urllib.error
    import json

    url = f"http://{host}:{port}/v1/context/{context_id}"
    console.print(f"Verifying context [bold cyan]{context_id}[/bold cyan]...")

    if not url.lower().startswith(("http://", "https://")):
        console.print("[bold red]Error:[/bold red] Invalid URL scheme")
        raise typer.Exit(1)

    try:
        req = urllib.request.Request(url)
        api_key = os.getenv("FABRA_API_KEY")
        if api_key:
            req.add_header("X-API-Key", api_key)

        with urllib.request.urlopen(req) as response:  # nosec B310
            if response.status != 200:
                console.print(
                    f"[bold red]Error:[/bold red] Server returned {response.status}"
                )
                raise typer.Exit(1)

            data = json.loads(response.read().decode())

            # Check if this is a ContextRecord with integrity metadata
            integrity = data.get("integrity", {})
            record_hash = integrity.get("record_hash", "")
            content_hash = integrity.get("content_hash", "")

            if not record_hash and not content_hash:
                # Try to verify from legacy format
                console.print(
                    "[yellow]Note:[/yellow] This context was stored in legacy format "
                    "(no integrity metadata). Cannot verify cryptographic integrity."
                )
                console.print(
                    "\n[dim]Tip: Contexts stored with Fabra 2.1+ include integrity hashes.[/dim]"
                )
                raise typer.Exit(0)

            # Verify content hash
            from fabra.utils.integrity import compute_content_hash

            content = data.get("content", "")
            computed_content_hash = compute_content_hash(content)

            content_valid = content_hash == computed_content_hash

            console.print("\n[bold]Integrity Check Results:[/bold]")

            if content_valid:
                console.print("  [green]✓[/green] Content hash matches")
                console.print(f"    [dim]Hash: {content_hash[:40]}...[/dim]")
            else:
                console.print("  [red]✗[/red] Content hash mismatch!")
                console.print(f"    [dim]Stored:   {content_hash[:40]}...[/dim]")
                console.print(
                    f"    [dim]Computed: {computed_content_hash[:40]}...[/dim]"
                )

            # Record hash verification would require full record reconstruction
            # which is complex - we just report what's stored
            if record_hash:
                console.print(f"  [dim]•[/dim] Record hash: {record_hash[:40]}...")
                console.print(
                    "    [dim](Full record hash verification requires local record)[/dim]"
                )

            console.print()

            if content_valid:
                console.print(
                    Panel(
                        "[bold green]✓ Integrity verified[/bold green]\n"
                        "Content has not been modified since recording.",
                        border_style="green",
                    )
                )
            else:
                console.print(
                    Panel(
                        "[bold red]✗ Integrity check failed[/bold red]\n"
                        "Content may have been modified or corrupted.",
                        border_style="red",
                    )
                )
                raise typer.Exit(1)

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
            f"[bold red]Connection Failed:[/bold red] {e}. "
            "Run [bold]fabra doctor[/bold] to check connectivity."
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@context_app.command(name="explain")
def explain_cmd(
    ctx_id: str = typer.Argument(..., help="The Context ID to trace"),
    host: str = typer.Option("127.0.0.1", help="Fabra server host"),
    port: int = typer.Option(8000, help="Fabra server port"),
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
        api_key = os.getenv("FABRA_API_KEY")
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
            f"[bold red]Connection Failed:[/bold red] {e}. Run [bold]fabra doctor[/bold] to check connectivity."
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@context_app.command(name="diff")
def context_diff_cmd(
    base_id: str = typer.Argument(..., help="Base (older) context ID"),
    comparison_id: str = typer.Argument(..., help="Comparison (newer) context ID"),
    host: str = typer.Option("127.0.0.1", help="Fabra server host"),
    port: int = typer.Option(8000, help="Fabra server port"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed per-item changes"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """
    Compare two context assemblies and show what changed.

    Examples:
        fabra context diff ctx_abc123 ctx_def456
        fabra context diff ctx_abc123 ctx_def456 --verbose
        fabra context diff ctx_abc123 ctx_def456 --json
    """
    import urllib.request
    import urllib.error
    import json

    # Fetch both contexts
    api_key = os.getenv("FABRA_API_KEY")

    def fetch_context(ctx_id: str) -> dict[str, Any]:
        url = f"http://{host}:{port}/v1/context/{ctx_id}"
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL scheme: {url}")
        req = urllib.request.Request(url)
        if api_key:
            req.add_header("X-API-Key", api_key)
        with urllib.request.urlopen(req) as response:  # nosec B310
            if response.status != 200:
                raise Exception(f"Server returned {response.status}")
            result: dict[str, Any] = json.loads(response.read().decode())
            return result

    try:
        console.print(f"Fetching context [cyan]{base_id[:12]}...[/cyan]")
        base_ctx = fetch_context(base_id)

        console.print(f"Fetching context [cyan]{comparison_id[:12]}...[/cyan]")
        comp_ctx = fetch_context(comparison_id)

        # Import comparison utilities
        from fabra.utils.compare import compare_contexts, format_diff_report
        from fabra.models import ContextLineage

        # Extract lineage from contexts
        base_lineage_data = base_ctx.get("lineage")
        comp_lineage_data = comp_ctx.get("lineage")

        if not base_lineage_data:
            console.print(
                f"[yellow]Warning: Base context {base_id} has no lineage data[/yellow]"
            )
            base_lineage_data = {
                "context_id": base_id,
                "timestamp": base_ctx.get("meta", {}).get(
                    "timestamp", datetime.now().isoformat()
                ),
                "features_used": [],
                "retrievers_used": [],
                "token_usage": base_ctx.get("meta", {}).get("token_usage", 0),
                "estimated_cost_usd": base_ctx.get("meta", {}).get("cost_usd", 0.0),
                "freshness_status": base_ctx.get("meta", {}).get(
                    "freshness_status", "unknown"
                ),
            }

        if not comp_lineage_data:
            console.print(
                f"[yellow]Warning: Comparison context {comparison_id} has no lineage data[/yellow]"
            )
            comp_lineage_data = {
                "context_id": comparison_id,
                "timestamp": comp_ctx.get("meta", {}).get(
                    "timestamp", datetime.now().isoformat()
                ),
                "features_used": [],
                "retrievers_used": [],
                "token_usage": comp_ctx.get("meta", {}).get("token_usage", 0),
                "estimated_cost_usd": comp_ctx.get("meta", {}).get("cost_usd", 0.0),
                "freshness_status": comp_ctx.get("meta", {}).get(
                    "freshness_status", "unknown"
                ),
            }

        base_lineage = ContextLineage(**base_lineage_data)
        comp_lineage = ContextLineage(**comp_lineage_data)

        # Compare
        diff = compare_contexts(
            base_lineage,
            comp_lineage,
            base_content=base_ctx.get("content"),
            comparison_content=comp_ctx.get("content"),
        )

        if json_output:
            console.print(diff.model_dump_json(indent=2))
        else:
            report = format_diff_report(diff, verbose=verbose)
            console.print(report)

            # Add color summary
            if diff.has_changes:
                console.print()
                if diff.features_added > 0:
                    console.print(
                        f"  [green]+{diff.features_added} features added[/green]"
                    )
                if diff.features_removed > 0:
                    console.print(
                        f"  [red]-{diff.features_removed} features removed[/red]"
                    )
                if diff.features_modified > 0:
                    console.print(
                        f"  [yellow]~{diff.features_modified} features modified[/yellow]"
                    )
                if diff.freshness_improved:
                    console.print("  [green]Freshness improved[/green]")
            else:
                console.print("\n[dim]No meaningful changes detected[/dim]")

    except urllib.error.URLError as e:
        console.print(
            f"[bold red]Connection Failed:[/bold red] {e}. Run [bold]fabra doctor[/bold] to check connectivity."
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
        None, envvar="FABRA_POSTGRES_URL", help="Postgres URL Override"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Preview changes without executing"
    ),
) -> None:
    """
    Manage vector indexes.
    Usage:
      fabra index create my_index --dimension=1536
      fabra index status my_index
      fabra index create my_index --dry-run  # Preview only
    """
    import asyncio
    from .store.postgres import PostgresOfflineStore
    from sqlalchemy import text

    url = postgres_url or os.getenv("FABRA_POSTGRES_URL")
    if not url:
        console.print("[bold red]Error:[/bold red] FABRA_POSTGRES_URL not set.")
        raise typer.Exit(1)

    async def run_action() -> None:
        try:
            store = PostgresOfflineStore(url)

            if action == "create":
                table_name = f"fabra_index_{name}"
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
                table = f"fabra_index_{name}"
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
    app_name: str = typer.Option("fabra-app", "--name", "-n", help="Application name"),
    region: str = typer.Option("iad", "--region", "-r", help="Deployment region"),
    output: str = typer.Option(".", "--output", "-o", help="Output directory"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview generated files without writing"
    ),
) -> None:
    """
    Generate deployment configuration for cloud platforms.

    Usage:
      fabra deploy fly --name my-app          # Generate fly.toml
      fabra deploy cloudrun --name my-app     # Generate Cloud Run config
      fabra deploy ecs --name my-app          # Generate ECS task definition
      fabra deploy --dry-run                  # Preview without writing
    """
    # Common Dockerfile for all deployments
    dockerfile = f"""# Auto-generated by Fabra CLI
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
CMD ["fabra", "serve", "{file}", "--host", "0.0.0.0", "--port", "8000"]
"""

    requirements_txt = """fabra>=2.2.0
redis>=4.0.0
asyncpg>=0.27.0
"""

    configs: dict[str, dict[str, str]] = {
        "fly": {
            "fly.toml": f"""# Auto-generated by Fabra CLI
app = "{app_name}"
primary_region = "{region}"

[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "8000"
  FABRA_ENV = "production"

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
            "service.yaml": f"""# Auto-generated by Fabra CLI
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
            - name: FABRA_ENV
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
            "cloudbuild.yaml": f"""# Auto-generated by Fabra CLI
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
        {{"name": "FABRA_ENV", "value": "production"}}
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
            "render.yaml": f"""# Auto-generated by Fabra CLI
services:
  - type: web
    name: {app_name}
    env: docker
    region: {region}
    plan: starter
    healthCheckPath: /health
    envVars:
      - key: FABRA_ENV
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
    "startCommand": "fabra serve {file} --host 0.0.0.0 --port $PORT",
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
            "fly secrets set FABRA_REDIS_URL=... FABRA_POSTGRES_URL=...",
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


@app.command(name="demo")
def demo_cmd(
    mode: str = typer.Option(
        "features",
        "--mode",
        "-m",
        help="Demo mode: 'features' (Feature Store) or 'context' (Context Store)",
    ),
    port: int = typer.Option(8000, help="Port to run demo server on"),
    no_test: bool = typer.Option(
        False,
        "--no-test",
        help="Skip the automatic demo request (useful for CI).",
    ),
) -> None:
    """
    Run an interactive demo of Fabra.

    This command starts a demo server with pre-seeded data and automatically
    tests an endpoint to show you a working response. No API keys required!

    Examples:
        fabra demo                    # Feature Store demo
        fabra demo --mode features    # Explicit Feature Store demo
        fabra demo --mode context     # Context Store demo (RAG without API keys)
    """
    import threading
    import time
    import urllib.request
    import urllib.error
    import json

    # Determine which demo module to use (shipped with the package so this works
    # from a clean install, without a repo checkout).
    demo_modules = {
        "features": "fabra.demos.demo_features",
        "context": "fabra.demos.demo_context",
    }

    if mode not in demo_modules:
        console.print(
            f"[bold red]Error:[/bold red] Unknown mode '{mode}'. Use 'features' or 'context'."
        )
        raise typer.Exit(1)

    demo_module = demo_modules[mode]

    demo_spec = importlib.util.find_spec(demo_module)
    file_path = demo_spec.origin if demo_spec else None
    if not file_path or not os.path.exists(file_path):
        console.print(
            f"[bold red]Error:[/bold red] Demo module '{demo_module}' not found.\n"
            "[dim]This should ship with Fabra. Try reinstalling.[/dim]"
        )
        raise typer.Exit(1)

    # Print startup banner
    console.print(
        Panel(
            "[bold blue]Fabra Demo[/bold blue]\n\n"
            f"[dim]Mode:[/dim] {mode.upper()}\n"
            f"[dim]File:[/dim] {file_path}",
            border_style="blue",
        )
    )

    console.print("\n[dim]Starting demo server...[/dim]\n")

    # Load the module to get the store
    sys.path.append(os.getcwd())
    sys.path.append(os.path.dirname(file_path))

    try:
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec for {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        store = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, FeatureStore):
                store = attr
                break

        if not store:
            console.print(
                "[bold red]Error:[/bold red] No FeatureStore instance found in demo file."
            )
            raise typer.Exit(1)

        # Start the server in a background thread
        app_instance = create_app(store)
        store.start()

        def run_server() -> None:
            import uvicorn

            config = uvicorn.Config(
                app_instance, host="127.0.0.1", port=port, log_level="warning"
            )
            server = uvicorn.Server(config)
            server.run()

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        # Wait for server to be ready by polling health endpoint
        console.print("[dim]Waiting for server to start...[/dim]")
        health_url = f"http://127.0.0.1:{port}/health"
        for _ in range(20):  # Try for up to 10 seconds
            try:
                with urllib.request.urlopen(health_url, timeout=1):  # nosec B310
                    break
            except (urllib.error.URLError, OSError):
                time.sleep(0.5)

        # Make a test request based on mode (optional).
        if mode == "features":
            test_url = (
                f"http://127.0.0.1:{port}/features/user_engagement?entity_id=user_123"
            )
            curl_cmd = f"curl {test_url}"
        else:  # context
            test_url = f"http://127.0.0.1:{port}/v1/context/chat_context"
            curl_cmd = (
                f'curl -X POST {test_url} -H "Content-Type: application/json" '
                '-d \'{"user_id":"user_123","query":"how do features work?"}\''
            )

        console.print(
            Panel(
                f"[bold green]Server is running at http://127.0.0.1:{port}[/bold green]\n\n"
                "[bold]Testing endpoint...[/bold]",
                border_style="green",
            )
        )

        # Show the curl command
        console.print(f"\n[bold]Try this:[/bold]\n  [cyan]{curl_cmd}[/cyan]\n")

        if not no_test:
            # Make the test request
            try:
                if mode == "features":
                    req = urllib.request.Request(test_url)
                else:
                    data = json.dumps(
                        {"user_id": "user_123", "query": "how do features work?"}
                    ).encode()
                    req = urllib.request.Request(
                        test_url,
                        data=data,
                        headers={"Content-Type": "application/json"},
                    )

                with urllib.request.urlopen(req, timeout=5) as response:  # nosec B310
                    result = json.loads(response.read().decode())
                    console.print("[bold]Response:[/bold]")
                    console.print(
                        Panel(
                            json.dumps(result, indent=2, default=str)[:500],
                            border_style="dim",
                        )
                    )

                    if mode == "features":
                        console.print(
                            "\n[green]✓[/green] Feature Store working! "
                            f"Got value: [bold]{result.get('value')}[/bold]"
                        )
                    else:
                        console.print(
                            "\n[green]✓[/green] Context Store working! "
                            f"Context ID: [bold]{result.get('id', 'N/A')[:12]}...[/bold]"
                        )

            except urllib.error.URLError as e:
                console.print(f"[yellow]Warning:[/yellow] Could not test endpoint: {e}")

        # Print help for next steps
        console.print(
            Panel(
                "[bold]Explore:[/bold]\n"
                f"  • API Docs: http://127.0.0.1:{port}/docs\n"
                f"  • Health: http://127.0.0.1:{port}/health\n"
                f"  • Metrics: http://127.0.0.1:{port}/metrics\n\n"
                "[bold]Learn more:[/bold]\n"
                "  • Docs: https://davidahmann.github.io/fabra/docs/\n"
                "  • Playground: https://fabraoss.vercel.app\n\n"
                "[dim]Press Ctrl+C to stop the server[/dim]",
                title="[bold blue]What's Next?[/bold blue]",
                border_style="blue",
            )
        )

        # Keep running until interrupted
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[dim]Stopping demo server...[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command(name="doctor")
def doctor_cmd(
    host: str = typer.Option("127.0.0.1", help="Fabra server host to check"),
    port: int = typer.Option(8000, help="Fabra server port to check"),
    redis_url: str = typer.Option(
        None, envvar="FABRA_REDIS_URL", help="Redis URL to check"
    ),
    postgres_url: str = typer.Option(
        None, envvar="FABRA_POSTGRES_URL", help="PostgreSQL URL to check"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """
    Diagnose and troubleshoot Fabra setup issues.

    Checks connectivity to services, validates configuration, and provides
    actionable recommendations for fixing issues.

    Examples:
        fabra doctor                           # Check local setup
        fabra doctor --host fabra.example.com  # Check remote server
        fabra doctor --verbose                 # Show detailed diagnostics
    """
    import socket
    import urllib.request
    import urllib.error
    import platform
    import json

    console.print(
        Panel(
            "[bold blue]Fabra Doctor[/bold blue]\n"
            "[dim]Diagnosing your Fabra setup...[/dim]",
            border_style="blue",
        )
    )

    checks_passed = 0
    checks_failed = 0
    warnings = 0

    def check_pass(msg: str) -> None:
        nonlocal checks_passed
        checks_passed += 1
        console.print(f"  [green]✓[/green] {msg}")

    def check_fail(msg: str, fix: str = "") -> None:
        nonlocal checks_failed
        checks_failed += 1
        console.print(f"  [red]✗[/red] {msg}")
        if fix:
            console.print(f"    [dim]→ Fix: {fix}[/dim]")

    def check_warn(msg: str, suggestion: str = "") -> None:
        nonlocal warnings
        warnings += 1
        console.print(f"  [yellow]![/yellow] {msg}")
        if suggestion:
            console.print(f"    [dim]→ {suggestion}[/dim]")

    # 1. System Information
    console.print("\n[bold]System Information[/bold]")
    console.print(f"  OS: {platform.system()} {platform.release()}")
    console.print(f"  Python: {platform.python_version()}")

    # 2. Check Python dependencies
    console.print("\n[bold]Python Dependencies[/bold]")
    required_packages = [
        ("fabra", "fabra"),
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("redis", "redis"),
        ("pydantic", "pydantic"),
        ("structlog", "structlog"),
    ]

    for display_name, import_name in required_packages:
        try:
            module = __import__(import_name)
            version = getattr(module, "__version__", "installed")
            check_pass(f"{display_name} ({version})")
        except ImportError:
            check_fail(f"{display_name} not installed", f"pip install {import_name}")

    # 3. Check environment variables
    console.print("\n[bold]Environment Variables[/bold]")
    env_vars = [
        ("FABRA_API_KEY", False, "API key for authentication"),
        ("FABRA_REDIS_URL", False, "Redis connection URL"),
        ("FABRA_POSTGRES_URL", False, "PostgreSQL connection URL"),
        ("FABRA_ENV", False, "Environment (development/production)"),
    ]

    for var, required, description in env_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            masked = value[:4] + "..." if len(value) > 8 else "***"
            check_pass(f"{var} = {masked}")
        elif required:
            check_fail(f"{var} not set", f"export {var}=<value>")
        else:
            check_warn(f"{var} not set", f"{description}")

    # 4. Check Fabra server connectivity
    console.print("\n[bold]Fabra Server[/bold]")
    server_url = f"http://{host}:{port}"

    try:
        health_url = f"{server_url}/health"
        req = urllib.request.Request(health_url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:  # nosec B310
            if response.status == 200:
                data = json.loads(response.read().decode())
                check_pass(f"Server responding at {server_url}")
                if verbose:
                    console.print(f"    [dim]Health response: {data}[/dim]")
            else:
                check_fail(
                    f"Server returned {response.status}",
                    "Check server logs for errors",
                )
    except urllib.error.URLError as e:
        check_fail(
            f"Cannot connect to {server_url}",
            f"Start server with: fabra serve <file> --port {port}",
        )
        if verbose:
            console.print(f"    [dim]Error: {e}[/dim]")
    except Exception as e:
        check_fail(f"Error checking server: {e}")

    # 5. Check Redis connectivity
    console.print("\n[bold]Redis Connection[/bold]")
    redis_url_to_check = redis_url or os.getenv("FABRA_REDIS_URL")

    if redis_url_to_check:
        try:
            from redis import Redis
            from urllib.parse import urlparse

            parsed = urlparse(redis_url_to_check)
            redis_host = parsed.hostname or "localhost"
            redis_port = parsed.port or 6379

            r = Redis(host=redis_host, port=redis_port, socket_timeout=3)
            info = r.ping()
            if info:
                check_pass(f"Redis connected at {redis_host}:{redis_port}")
                if verbose:
                    redis_info = r.info()
                    console.print(
                        f"    [dim]Redis version: {redis_info.get('redis_version', 'unknown')}[/dim]"
                    )
                    console.print(
                        f"    [dim]Memory used: {redis_info.get('used_memory_human', 'unknown')}[/dim]"
                    )
            r.close()
        except ImportError:
            check_fail("redis package not installed", "pip install redis")
        except Exception as e:
            check_fail(f"Redis connection failed: {e}", "Check Redis is running")
    else:
        check_warn(
            "Redis URL not configured",
            "Using in-memory store (data won't persist)",
        )

    # 6. Check PostgreSQL connectivity
    console.print("\n[bold]PostgreSQL Connection[/bold]")
    postgres_url_to_check = postgres_url or os.getenv("FABRA_POSTGRES_URL")

    if postgres_url_to_check:
        try:
            import asyncpg
            import asyncio

            async def check_postgres() -> bool:
                try:
                    conn = await asyncio.wait_for(
                        asyncpg.connect(postgres_url_to_check), timeout=5
                    )
                    version = await conn.fetchval("SELECT version()")
                    await conn.close()
                    check_pass("PostgreSQL connected")
                    if verbose:
                        console.print(f"    [dim]{version[:60]}...[/dim]")
                    return True
                except Exception as e:
                    check_fail(
                        f"PostgreSQL connection failed: {e}",
                        "Check PostgreSQL is running and credentials are correct",
                    )
                    return False

            asyncio.run(check_postgres())
        except ImportError:
            check_fail("asyncpg package not installed", "pip install asyncpg")
    else:
        check_warn(
            "PostgreSQL URL not configured",
            "Offline store features unavailable (context replay, lineage)",
        )

    # 7. Check common ports
    console.print("\n[bold]Port Availability[/bold]")
    ports_to_check = [
        (8000, "Fabra API"),
        (8501, "Fabra UI"),
        (6379, "Redis"),
        (5432, "PostgreSQL"),
    ]

    for check_port, service in ports_to_check:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", check_port))
        sock.close()

        if result == 0:
            if check_port == port:
                check_pass(f"Port {check_port} ({service}) - in use (expected)")
            else:
                check_warn(f"Port {check_port} ({service}) - in use")
        else:
            if check_port == port:
                check_warn(
                    f"Port {check_port} ({service}) - not listening",
                    f"Start with: fabra serve <file> --port {check_port}",
                )

    # 8. Check API endpoints (if server is running)
    if checks_failed == 0 or server_url:
        console.print("\n[bold]API Endpoints[/bold]")
        endpoints = [
            ("/health", "GET", "Health check"),
            ("/metrics", "GET", "Prometheus metrics"),
            ("/docs", "GET", "OpenAPI documentation"),
        ]

        for endpoint, method, description in endpoints:
            try:
                url = f"{server_url}{endpoint}"
                req = urllib.request.Request(url, method=method)
                with urllib.request.urlopen(req, timeout=3) as response:  # nosec B310
                    if response.status == 200:
                        check_pass(f"{method} {endpoint} - {description}")
                    else:
                        check_warn(f"{method} {endpoint} returned {response.status}")
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    check_pass(f"{method} {endpoint} - requires auth (OK)")
                else:
                    check_warn(f"{method} {endpoint} - HTTP {e.code}")
            except Exception:  # noqa: S110  # nosec B110
                pass  # Server not running, already reported above

    # Summary
    console.print("\n" + "─" * 50)

    if checks_failed == 0 and warnings == 0:
        console.print(
            Panel(
                f"[bold green]All {checks_passed} checks passed![/bold green]\n"
                "Your Fabra setup looks healthy.",
                border_style="green",
            )
        )
    elif checks_failed == 0:
        console.print(
            Panel(
                f"[bold yellow]{checks_passed} passed, {warnings} warnings[/bold yellow]\n"
                "Fabra should work, but some features may be limited.",
                border_style="yellow",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold red]{checks_failed} failed[/bold red], {checks_passed} passed, {warnings} warnings\n"
                "Please fix the issues above to ensure Fabra works correctly.",
                border_style="red",
            )
        )

    # Recommendations
    if checks_failed > 0 or warnings > 0:
        console.print("\n[bold]Recommendations:[/bold]")
        if not redis_url_to_check:
            console.print(
                "  1. [dim]Set up Redis for caching: docker run -d -p 6379:6379 redis[/dim]"
            )
        if not postgres_url_to_check:
            console.print(
                "  2. [dim]Set up PostgreSQL for offline store: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres[/dim]"
            )
        console.print(
            "\n[dim]Run 'fabra doctor --verbose' for more detailed diagnostics[/dim]"
        )

    raise typer.Exit(1 if checks_failed > 0 else 0)


if __name__ == "__main__":
    app()
