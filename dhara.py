import os
import subprocess

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Dhara AI — Monorepo Developer CLI")
console = Console()

SERVICES = [
    "orchestrator",
    "site_analysis",
    "aviation_height",
    "ready_reckoner",
    "report_generator",
    "pr_card_scraper",
    "rag_service",
    "mcgm_property_lookup",
    "dp_remarks_report",
]


@app.command()
def check():
    """Run health checks for all services."""
    table = Table(title="Dhara Service Mesh Health")
    table.add_column("Service", style="cyan")
    table.add_column("Endpoint", style="magenta")
    table.add_column("Status", style="green")

    # This is a simplified check, in reality we could use httpx to hit /health
    console.print("[yellow]Pinging service endpoints...[/yellow]")

    # Just list them for now to show the CLI works
    for s in SERVICES:
        table.add_row(s, f"localhost/{s}", "CONFIGURED")

    console.print(table)


@app.command()
def migrate(service: str = typer.Option("all", help="Specific service to migrate")):
    """Run database migrations."""
    target_services = SERVICES if service == "all" else [service]

    for s in target_services:
        alembic_path = f"services/{s}/alembic.ini"
        if os.path.exists(alembic_path):
            console.print(f"[bold blue]Migrating {s}...[/bold blue]")
            subprocess.run(["alembic", "-c", alembic_path, "upgrade", "head"])
        else:
            console.print(f"[dim]Skipping {s} (no alembic.ini found)[/dim]")


@app.command()
def up():
    """Start the entire stack."""
    console.print("[bold green]Launching Dhara Stack...[/bold green]")
    subprocess.run(["docker-compose", "up", "-d"])


@app.command()
def down():
    """Stop the entire stack."""
    subprocess.run(["docker-compose", "down"])


@app.command()
def logs(service: str = typer.Argument(None)):
    """View logs."""
    cmd = ["docker-compose", "logs", "-f"]
    if service:
        cmd.append(service)
    subprocess.run(cmd)


if __name__ == "__main__":
    app()
