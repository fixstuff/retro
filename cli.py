#!/usr/bin/env python3
"""Retro Code Builder — CLI for extracting code from Compute! magazine."""

import asyncio
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from archive_client import ArchiveClient
from code_extractor import extract_listings, clean_listing, identify_platform

console = Console()
client = ArchiveClient()


def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@click.group()
def cli():
    """RETRO CODE BUILDER — Extract code from Compute! magazine."""
    pass


@cli.command()
@click.option("-q", "--query", default="", help="Search query")
@click.option("-p", "--page", default=1, help="Results page")
@click.option("-n", "--limit", default=20, help="Results per page")
def issues(query, page, limit):
    """List/search Compute! magazine issues."""
    data = run_async(client.search_issues(query, page, limit))

    table = Table(title=f"COMPUTE! ISSUES ({data['total']} total)")
    table.add_column("Date", style="yellow")
    table.add_column("Identifier", style="green")
    table.add_column("Title", style="cyan")
    table.add_column("Pages", justify="right")

    for issue in data["issues"]:
        date = issue.get("date", "?")[:10]
        pages = str(issue.get("imagecount", "?"))
        table.add_row(date, issue["identifier"], issue.get("title", ""), pages)

    console.print(table)


@cli.command()
@click.argument("identifier")
def info(identifier):
    """Show details for a specific issue."""
    metadata = run_async(client.get_metadata(identifier))
    md = metadata.get("metadata", {})

    title = md.get("title", identifier)
    if isinstance(title, list):
        title = title[0]

    page_count = run_async(client.get_page_count(identifier))

    console.print(Panel(
        f"[yellow]{title}[/]\n"
        f"Date: {md.get('date', '?')}\n"
        f"Pages: {page_count}\n"
        f"ID: {identifier}\n"
        f"URL: https://archive.org/details/{identifier}",
        title="Issue Info",
    ))


@cli.command()
@click.argument("identifier")
@click.argument("page", type=int)
@click.option("-n", "--num-pages", default=3, help="Number of pages to scan")
def extract(identifier, page, num_pages):
    """Extract code listings from a page (scans multiple pages)."""
    console.print(f"[yellow]Scanning pages {page}-{page + num_pages - 1}...[/]")

    page_texts = run_async(client.get_page_text_range(identifier, page, num_pages))
    all_text = "\n".join(page_texts.get(p, "") for p in sorted(page_texts.keys()))

    if not all_text.strip():
        console.print("[red]No OCR text available for these pages[/]")
        return

    listings = extract_listings(all_text)
    platform = identify_platform(all_text)

    if not listings:
        console.print(f"[red]No code listings found on pages {list(page_texts.keys())}[/]")
        console.print(f"Platform detected: {platform}")
        return

    console.print(f"[green]Found {len(listings)} listing(s) — Platform: {platform}[/]\n")

    for i, listing in enumerate(listings):
        cleaned = clean_listing(listing["code"])
        console.print(Panel(
            Syntax(cleaned, "basic", theme="monokai", line_numbers=True),
            title=f"Listing {i + 1} — Lines {listing['first_line']}-{listing['last_line']} ({listing['line_count']} lines)",
            subtitle=platform,
        ))
        console.print()


@cli.command()
@click.argument("identifier")
@click.argument("page", type=int)
def text(identifier, page):
    """Show raw OCR text for a page."""
    text = run_async(client.get_page_text(identifier, page))
    if text:
        console.print(Panel(text, title=f"Page {page} OCR Text"))
    else:
        console.print("[red]No OCR text available[/]")


@cli.command()
@click.argument("identifier")
@click.option("--start", default=0, help="Start page")
@click.option("--end", default=None, type=int, help="End page")
def scan(identifier, start, end):
    """Scan an entire issue for code listings."""
    page_count = run_async(client.get_page_count(identifier))
    if end is None:
        end = page_count

    console.print(f"[yellow]Scanning pages {start}-{end} of {identifier}...[/]")

    all_listings = []
    for p in range(start, end, 5):
        chunk_end = min(p + 5, end)
        page_texts = run_async(client.get_page_text_range(identifier, p, chunk_end - p))
        combined = "\n".join(page_texts.get(i, "") for i in sorted(page_texts.keys()))
        listings = extract_listings(combined)
        platform = identify_platform(combined)

        for listing in listings:
            listing["cleaned"] = clean_listing(listing["code"])
            listing["platform"] = platform
            listing["approx_page"] = p
            all_listings.append(listing)

        if listings:
            console.print(f"  [green]Pages {p}-{chunk_end-1}: {len(listings)} listing(s)[/]")

    console.print(f"\n[green]Total: {len(all_listings)} listings found[/]\n")

    for i, listing in enumerate(all_listings):
        console.print(Panel(
            Syntax(listing["cleaned"], "basic", theme="monokai", line_numbers=True),
            title=f"Listing {i + 1} (~page {listing['approx_page']}) — Lines {listing['first_line']}-{listing['last_line']}",
            subtitle=listing["platform"],
        ))
        console.print()


@cli.command()
def serve():
    """Start the web interface."""
    import uvicorn
    console.print("[green]Starting Retro Code Builder web interface on port 8580...[/]")
    uvicorn.run("app:app", host="0.0.0.0", port=8580)


if __name__ == "__main__":
    cli()
