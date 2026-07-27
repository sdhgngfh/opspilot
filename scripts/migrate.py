from __future__ import annotations

import argparse

from app.config import PROJECT_ROOT, get_settings
from app.migrations import PostgresMigrator
from app.service import RAGService


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply checksummed PostgreSQL migrations.")
    parser.add_argument(
        "--status",
        action="store_true",
        help="Only show migration status; do not change the database.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Alias for --status, suitable for deployment planning.",
    )
    args = parser.parse_args()
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL 未配置")

    migrator = PostgresMigrator(
        settings.database_url,
        PROJECT_ROOT / "migrations",
    )
    states = migrator.status() if args.status or args.dry_run else migrator.apply()
    for state in states:
        print(f"{state.version} {state.name}: {state.status}")
    if any(item.status == "drifted" for item in states):
        raise SystemExit("检测到迁移漂移")
    if not args.status and not args.dry_run and settings.index_backend == "postgres":
        service = RAGService(settings)
        service.ensure_ready()
    if args.status or args.dry_run:
        if any(item.status != "applied" for item in states):
            raise SystemExit("存在待应用迁移")
        print("PostgreSQL migrations are current.")
    else:
        print("PostgreSQL application schema is ready.")


if __name__ == "__main__":
    main()
