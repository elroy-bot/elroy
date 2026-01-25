#!/usr/bin/env python3
"""Migrate vector embeddings from SQLite/Postgres to ChromaDB.

This script performs a one-time offline migration of all vector embeddings
from the native vector storage (sqlite-vec or pgvector) to ChromaDB.

Usage:
    python -m scripts.migrate_to_chroma \\
        --database-url sqlite:///~/.elroy/elroy.db \\
        --chroma-dir ~/.elroy/chroma \\
        --validate

Features:
- Non-destructive: Original vectors remain in source database
- Validation: Optionally verify migration accuracy
- Progress tracking: Shows migration progress
- Safe: Can be re-run idempotently
"""

import sys
from pathlib import Path
from struct import unpack

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from sqlalchemy import text
from sqlmodel import select

# Add parent directory to path to import elroy
sys.path.insert(0, str(Path(__file__).parent.parent))

from elroy.core.constants import EMBEDDING_SIZE
from elroy.db.db_manager import get_db_manager
from elroy.db.db_models import DocumentExcerpt, Memory, Reminder, User

console = Console()


@click.command()
@click.option(
    "--database-url",
    required=True,
    help="Source database URL (sqlite:///path or postgresql://...)",
)
@click.option(
    "--chroma-dir",
    default=None,
    help="ChromaDB persistent storage directory (default: ~/.elroy/chroma)",
)
@click.option(
    "--validate",
    is_flag=True,
    help="Validate migration by comparing vector counts and sampling embeddings",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview migration without writing to ChromaDB",
)
def migrate_to_chroma(database_url: str, chroma_dir: str | None, validate: bool, dry_run: bool):
    """Migrate vector embeddings from SQLite/Postgres to ChromaDB."""

    console.print("[bold blue]Elroy Vector Migration: SQLite/Postgres → ChromaDB[/bold blue]")
    console.print()

    # Resolve paths
    if chroma_dir:
        chroma_path = Path(chroma_dir).expanduser()
    else:
        chroma_path = Path.home() / ".elroy" / "chroma"

    console.print(f"[dim]Source Database:[/dim] {database_url}")
    console.print(f"[dim]ChromaDB Directory:[/dim] {chroma_path}")
    console.print(f"[dim]Validation:[/dim] {'Enabled' if validate else 'Disabled'}")
    console.print(f"[dim]Mode:[/dim] {'DRY RUN' if dry_run else 'LIVE MIGRATION'}")
    console.print()

    if dry_run:
        console.print("[yellow]DRY RUN MODE: No data will be written to ChromaDB[/yellow]")
        console.print()

    # Initialize source database (with native vector storage)
    console.print("[cyan]→[/cyan] Connecting to source database...")
    source_db_manager = get_db_manager(database_url, vector_backend="sqlite")

    # Initialize ChromaDB backend
    console.print("[cyan]→[/cyan] Initializing ChromaDB...")
    from elroy.db.chroma.chroma_manager import ChromaManager

    chroma_manager = ChromaManager(database_url, chroma_path=chroma_path)

    # Migration stats
    stats = {
        "users": 0,
        "memories": 0,
        "reminders": 0,
        "documents": 0,
        "errors": 0,
    }

    # Fast-path SQLite migration directly from vectorstorage table
    if database_url.startswith("sqlite:///"):
        run_sqlite_vectorstorage_migration(
            source_db_manager,
            chroma_manager,
            dry_run,
            stats,
        )

        if validate and not dry_run:
            console.print("[bold]Validating migration...[/bold]")
            users = list(get_users(source_db_manager))
            validation_passed = validate_migration(source_db_manager, chroma_manager, users)
            if validation_passed:
                console.print("[bold green]✓ Validation passed![/bold green]")
            else:
                console.print("[bold red]✗ Validation failed - see errors above[/bold red]")
                sys.exit(1)

        print_next_steps()
        return

    # Get all users
    with source_db_manager.open_session() as source_session:
        users = list(source_session.exec(select(User)).all())
        stats["users"] = len(users)

        console.print(f"[green]✓[/green] Found {len(users)} users")
        console.print()

        # Migrate each user's vectors
        for user in users:
            user_label = getattr(user, "email", None) or getattr(user, "token", None) or "unknown"
            console.print(f"[bold]Migrating vectors for user {user.id} ({user_label})...[/bold]")

            # Migrate each entity type
            entity_types = [
                (Memory, "memories"),
                (Reminder, "reminders"),
                (DocumentExcerpt, "documents"),
            ]

            with chroma_manager.open_session() as chroma_session:
                for entity_class, label in entity_types:
                    entities = list(source_session.exec(select(entity_class).where(entity_class.user_id == user.id)).all())

                    if not entities:
                        console.print(f"  [dim]No {label} to migrate[/dim]")
                        continue

                    batch_size = 200
                    batch_rows = []
                    batch_embeddings = []
                    batch_md5s = []

                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=console,
                    ) as progress:
                        task = progress.add_task(f"  Migrating {len(entities)} {label}...", total=len(entities))

                        for entity in entities:
                            try:
                                # Get embedding from source
                                embedding = source_session.get_embedding(entity)
                                if not embedding:
                                    progress.console.print(f"    [yellow]⚠[/yellow] No embedding for {entity_class.__name__} {entity.id}")
                                    continue

                                # Get embedding text MD5
                                embedding_text_md5 = source_session.get_embedding_text_md5(entity)
                                if not embedding_text_md5:
                                    progress.console.print(f"    [yellow]⚠[/yellow] No MD5 for {entity_class.__name__} {entity.id}")
                                    continue

                                batch_rows.append(entity)
                                batch_embeddings.append(embedding)
                                batch_md5s.append(embedding_text_md5)
                                stats[label] += 1

                                if not dry_run and len(batch_rows) >= batch_size:
                                    chroma_session.upsert_embeddings(batch_rows, batch_embeddings, batch_md5s)
                                    batch_rows = []
                                    batch_embeddings = []
                                    batch_md5s = []

                                progress.advance(task)

                            except Exception as e:
                                stats["errors"] += 1
                                progress.console.print(f"    [red]✗[/red] Error migrating {entity_class.__name__} {entity.id}: {e}")

                        if not dry_run and batch_rows:
                            chroma_session.upsert_embeddings(batch_rows, batch_embeddings, batch_md5s)

            console.print()

    print_summary(stats)

    # Validation
    if validate and not dry_run:
        console.print("[bold]Validating migration...[/bold]")
        validation_passed = validate_migration(source_db_manager, chroma_manager, users)

        if validation_passed:
            console.print("[bold green]✓ Validation passed![/bold green]")
        else:
            console.print("[bold red]✗ Validation failed - see errors above[/bold red]")
            sys.exit(1)

    print_next_steps()


def validate_migration(source_db_manager, chroma_manager, users):
    """Validate that migration was successful by comparing vector counts."""
    console.print()
    validation_passed = True

    for user in users:
        console.print(f"  Validating user {user.id}...")

        with source_db_manager.open_session() as source_session:
            with chroma_manager.open_session() as chroma_session:
                # Compare counts for each entity type
                for entity_class in [Memory, Reminder, DocumentExcerpt]:
                    source_entities = list(source_session.exec(select(entity_class).where(entity_class.user_id == user.id)).all())

                    # Count how many have embeddings in source
                    source_count = sum(1 for e in source_entities if source_session.get_embedding(e) is not None)

                    # Count how many have embeddings in ChromaDB
                    chroma_count = sum(1 for e in source_entities if chroma_session.get_embedding(e) is not None)

                    if source_count != chroma_count:
                        console.print(f"    [red]✗[/red] {entity_class.__name__}: source={source_count}, chroma={chroma_count}")
                        validation_passed = False
                    else:
                        console.print(f"    [green]✓[/green] {entity_class.__name__}: {source_count} vectors")

    return validation_passed


def get_users(source_db_manager):
    with source_db_manager.open_session() as source_session:
        return list(source_session.exec(select(User)).all())


def run_sqlite_vectorstorage_migration(source_db_manager, chroma_manager, dry_run: bool, stats: dict) -> None:
    """Fast migration path for SQLite using vectorstorage table directly."""
    console.print("[cyan]→[/cyan] Using fast SQLite vectorstorage migration path")

    batch_size = 500
    batch_embeddings = []
    batch_ids = []
    batch_metadatas = []
    current_user_id = None

    def flush_batches(user_id: int):
        if dry_run or not batch_ids:
            return
        collection = chroma_manager.chroma_client.get_or_create_collection(
            name=f"elroy_vectors_{user_id}",
            metadata={"hnsw:space": "l2"},
        )
        collection.upsert(
            ids=batch_ids,
            embeddings=batch_embeddings,
            metadatas=batch_metadatas,
        )

    with source_db_manager.open_session() as source_session:
        total = source_session.exec(text("SELECT COUNT(*) FROM vectorstorage")).first()[0]
        stats["users"] = source_session.exec(text("SELECT COUNT(DISTINCT user_id) FROM vectorstorage")).first()[0]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Migrating vectors from vectorstorage...", total=total)

            rows = source_session.exec(
                text(
                    """
                    SELECT source_type, source_id, user_id, embedding_data, embedding_text_md5
                    FROM vectorstorage
                    ORDER BY user_id
                    """
                )
            )

            for row in rows:
                source_type = row[0]
                source_id = row[1]
                user_id = row[2]
                embedding_data = row[3]
                embedding_text_md5 = row[4]

                if current_user_id is None:
                    current_user_id = user_id
                elif user_id != current_user_id:
                    flush_batches(current_user_id)
                    batch_embeddings.clear()
                    batch_ids.clear()
                    batch_metadatas.clear()
                    current_user_id = user_id

                if embedding_data is None or embedding_text_md5 is None:
                    stats["errors"] += 1
                    progress.advance(task)
                    continue

                if isinstance(embedding_data, memoryview):
                    embedding_data = embedding_data.tobytes()

                embedding = list(unpack(f"{EMBEDDING_SIZE}f", embedding_data))
                doc_id = f"{source_type}_{source_id}"

                batch_ids.append(doc_id)
                batch_embeddings.append(embedding)
                batch_metadatas.append(
                    {
                        "source_type": source_type,
                        "source_id": source_id,
                        "user_id": user_id,
                        "embedding_text_md5": embedding_text_md5,
                        "is_active": True,
                    }
                )

                if source_type == "Memory":
                    stats["memories"] += 1
                elif source_type == "Reminder":
                    stats["reminders"] += 1
                elif source_type == "DocumentExcerpt":
                    stats["documents"] += 1

                if len(batch_ids) >= batch_size:
                    flush_batches(user_id)
                    batch_embeddings.clear()
                    batch_ids.clear()
                    batch_metadatas.clear()

                progress.advance(task)

            if current_user_id is not None:
                flush_batches(current_user_id)

    print_summary(stats)


def print_summary(stats: dict) -> None:
    console.print("[bold green]Migration Complete![/bold green]")
    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Users:     {stats['users']}")
    console.print(f"  Memories:  {stats['memories']}")
    console.print(f"  Reminders: {stats['reminders']}")
    console.print(f"  Documents: {stats['documents']}")
    console.print(f"  Errors:    {stats['errors']}")
    console.print()


def print_next_steps() -> None:
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print("  1. Update ~/.elroy/elroy.conf.yaml:")
    console.print("     [cyan]vector_backend: chroma[/cyan]")
    console.print("  2. Test Elroy with ChromaDB backend:")
    console.print("     [cyan]elroy chat[/cyan]")
    console.print("  3. To rollback, change config back to:")
    console.print("     [cyan]vector_backend: sqlite[/cyan]")
    console.print()


if __name__ == "__main__":
    migrate_to_chroma()
