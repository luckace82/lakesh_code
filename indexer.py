#!/usr/bin/env python3
"""
Lakesh codebase indexer.
Usage: python indexer.py [project_root]
"""

import sys
import os
from pathlib import Path

try:
    import ollama
    import chromadb
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
except ImportError:
    print("Run: pip install ollama chromadb rich")
    sys.exit(1)

console = Console()

EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".html", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml",
    ".md", ".txt", ".env.example",
    ".sh", ".sql"
}

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", ".chroma", "migrations", ".mypy_cache"
}

def get_files(root: str):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip unwanted directories in-place
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if Path(fname).suffix in EXTENSIONS:
                files.append(os.path.join(dirpath, fname))
    return files

def index_repo(root: str = "."):
    root = os.path.abspath(root)
    console.print(f"\n[bold blue]Lakesh Indexer[/bold blue] — indexing [dim]{root}[/dim]\n")

    client = chromadb.PersistentClient(path=os.path.join(root, ".chroma"))

    try:
        client.delete_collection("codebase")
    except:
        pass
    col = client.create_collection("codebase")

    files = get_files(root)
    console.print(f"Found [bold]{len(files)}[/bold] files to index\n")

    indexed = 0
    skipped = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console
    ) as progress:
        task = progress.add_task("Indexing...", total=len(files))

        for fpath in files:
            progress.update(task, description=f"[dim]{os.path.relpath(fpath, root)}[/dim]")
            try:
                content = Path(fpath).read_text(errors="ignore")
                if not content.strip():
                    skipped += 1
                    progress.advance(task)
                    continue

                content = content[:8000]

                emb = ollama.embeddings(
                    model="nomic-embed-text",
                    prompt=content
                )["embedding"]

                col.upsert(
                    ids=[fpath],
                    embeddings=[emb],
                    documents=[content],
                    metadatas=[{"path": fpath, "root": root}]
                )
                indexed += 1
            except Exception as e:
                console.print(f"[dim red]  skip {os.path.basename(fpath)}: {e}[/dim red]")
                skipped += 1

            progress.advance(task)

    console.print(f"\n[green]✓[/green] Indexed [bold]{indexed}[/bold] files, skipped {skipped}")
    console.print(f"[dim]Index saved to {root}/.chroma[/dim]\n")

if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    index_repo(root)
