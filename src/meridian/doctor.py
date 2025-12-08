import os
import sys
import types
import platform
import structlog
from typing import Optional, Dict, Any, List
import importlib.util

logger = structlog.get_logger()

try:
    from rich.console import Console
    from rich.table import Table

    console: Optional[Console] = Console()
except ImportError:
    console = None  # Fallback if rich not installed (though it is a dep)


def check_env_vars() -> List[Dict[str, Any]]:
    # Check essential env vars
    vars_to_check = [
        "MERIDIAN_ENV",
        "MERIDIAN_REDIS_URL",
        "MERIDIAN_POSTGRES_URL",
    ]
    results = []
    for v in vars_to_check:
        val = os.environ.get(v)
        if val:
            # Mask secrets (simple heuristic: if URL contains password)
            if "://" in val and "@" in val:
                # redis://:pass@host -> redis://:***@host
                parts = val.split("@")
                safe_val = parts[0].split(":")[0] + ":***@" + parts[1]
            else:
                safe_val = val
            results.append({"name": v, "status": "✅ Set", "value": safe_val})
        else:
            results.append(
                {"name": v, "status": "⚠️ Unset", "value": "None (Using defaults?)"}
            )
    return results


def check_redis(redis_url: Optional[str]) -> Dict[str, Any]:
    if not redis_url:
        # Try default localhost if not set, or skip
        return {"name": "Redis", "status": "⏭️ Skipped", "details": "No URL provided"}

    try:
        import redis

        r = redis.from_url(redis_url)
        r.ping()
        return {
            "name": "Redis",
            "status": "✅ Connected",
            "details": f"Ping successful to {redis_url.split('@')[-1]}",
        }
    except ImportError:
        return {
            "name": "Redis",
            "status": "❌ Error",
            "details": "redis-py not installed",
        }
    except Exception as e:
        return {
            "name": "Redis",
            "status": "❌ Failed",
            "details": f"{e}. Fix: Try 'docker run -d -p 6379:6379 redis:alpine'",
        }


def check_postgres(pg_url: Optional[str]) -> Dict[str, Any]:
    if not pg_url:
        return {"name": "Postgres", "status": "⏭️ Skipped", "details": "No URL provided"}

    try:
        import sqlalchemy

        engine = sqlalchemy.create_engine(pg_url)
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        return {
            "name": "Postgres",
            "status": "✅ Connected",
            "details": "SELECT 1 successful",
        }
    except ImportError:
        return {
            "name": "Postgres",
            "status": "❌ Error",
            "details": "sqlalchemy not installed",
        }
    except Exception as e:
        return {"name": "Postgres", "status": "❌ Failed", "details": str(e)}


def run_doctor() -> None:
    """Diagnose configuration and connectivity."""
    if console:
        console.print("[bold blue]🩺 Meridian Doctor[/bold blue]")
        console.print(f"Python: {platform.python_version()} ({sys.executable})")
        console.print(f"Platform: {platform.platform()}")
    else:
        print("Meridian Doctor")

    # 1. Env Vars
    env_results = check_env_vars()

    if console:
        table = Table(title="Environment Variables")
        table.add_column("Variable", style="cyan")
        table.add_column("Status")
        table.add_column("Value", style="dim")
        for res in env_results:
            table.add_row(res["name"], res["status"], res["value"])
        console.print(table)
    else:
        print("\nEnvironment Variables:")
        for res in env_results:
            print(f"{res['name']}: {res['status']} ({res['value']})")

    # 2. Connectivity
    redis_url = os.environ.get("MERIDIAN_REDIS_URL") or os.environ.get("REDIS_URL")
    pg_url = os.environ.get("MERIDIAN_POSTGRES_URL") or os.environ.get("POSTGRES_URL")

    conn_results = [check_redis(redis_url), check_postgres(pg_url)]

    if console:
        table = Table(title="Connectivity")
        table.add_column("Service", style="magenta")
        table.add_column("Status")
        table.add_column("Details", style="dim")
        for res in conn_results:
            table.add_row(res["name"], res["status"], res["details"])
        console.print(table)
    else:
        print("\nConnectivity:")
        for res in conn_results:
            print(f"{res['name']}: {res['status']} - {res['details']}")

    # 3. Dependencies
    if console:
        console.print("\n[bold]Dependencies[/bold]")
    else:
        print("\nDependencies:")

    try:
        toml_loader: Optional[types.ModuleType] = None
        if sys.version_info >= (3, 11):
            import tomllib

            toml_loader = tomllib
        else:
            # Fallback for older python if tomllib not present
            try:
                import tomli

                toml_loader = tomli
            except ImportError:
                pass

        required_deps: List[str] = []

        # Read pyproject.toml
        pyproject_path = os.path.join(os.getcwd(), "pyproject.toml")
        if os.path.exists(pyproject_path) and toml_loader:
            with open(pyproject_path, "rb") as f:
                data = toml_loader.load(f)
                # project.dependencies is a list of strings like "fastapi>=0.68.0"
                deps_raw = data.get("project", {}).get("dependencies", [])
                # Parse out package names (simple split)
                import re

                for d in deps_raw:
                    # Match name at start of string before any operator
                    match = re.match(r"^([a-zA-Z0-9_\-]+)", d)
                    if match:
                        required_deps.append(
                            match.group(1).replace("-", "_")
                        )  # normalize to import name approx
        else:
            # Fallback to hardcoded if pyproject not found or parser missing
            required_deps = [
                "fastapi",
                "uvicorn",
                "redis",
                "sqlalchemy",
                "duckdb",
                "apscheduler",
                "structlog",
            ]

        missing = []
        for dep in required_deps:
            # Handle package vs import name naming differences manually for common libs
            import_name = dep
            if dep == "prometheus_client":
                import_name = "prometheus_client"
            if dep == "python_multipart":
                import_name = "multipart"

            if not importlib.util.find_spec(import_name):
                missing.append(dep)

        if missing:
            msg = f"❌ Missing dependencies: {', '.join(missing)}"
            if console:
                console.print(f"[red]{msg}[/red]")
            else:
                print(msg)
        else:
            msg = f"✅ All {len(required_deps)} core dependencies installed."
            if console:
                console.print(f"[green]{msg}[/green]")
            else:
                print(msg)

    except Exception as e:
        if console:
            console.print(
                f"[yellow]Could not verify dependencies automatically: {e}[/yellow]"
            )
        else:
            print(f"Could not verify dependencies automatically: {e}")
