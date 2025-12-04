import typer
import os
import sys
from rich.console import Console
from rich.panel import Panel

app = typer.Typer()
console = Console()


@app.command()
def start(
    file: str = typer.Argument(
        ..., help="Path to the feature definition file (e.g., features.py)"
    ),
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
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
            style="bold indigo",
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
        __import__(module_name)
        console.print(f"[green]Successfully loaded features from {file}[/green]")

        # TODO: Start the scheduler and server
        # store.start()
        # uvicorn.run(app, host=host, port=port)

    except Exception as e:
        console.print(f"[bold red]Error loading features:[/bold red] {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
