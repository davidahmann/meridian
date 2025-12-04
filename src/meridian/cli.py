import typer
import uvicorn
import os
import sys
import importlib.util
from rich.console import Console
from rich.panel import Panel
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
    # We need to add the current directory to sys.path so we can import the file
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

        console.print(f"[green]Successfully loaded features from {file}[/green]")

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

        # Start scheduler and server
        store.start()

        # Set API key in env for the server to pick up
        if api_key:
            os.environ["MERIDIAN_API_KEY"] = api_key

        app = create_app(store)
        uvicorn.run(app, host=host, port=port)

    except Exception as e:
        console.print(f"[bold red]Error loading features:[/bold red] {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
