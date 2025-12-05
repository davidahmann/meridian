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


@app.callback()
def callback() -> None:
    """
    Meridian CLI
    """


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

            # Mock metrics for now (since we can't easily hook into uvicorn stats from here without middleware)
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


if __name__ == "__main__":
    app()
