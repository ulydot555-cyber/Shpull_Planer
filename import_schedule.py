from __future__ import annotations

from database import get_connection
from database import init_database
from database import upsert_external_task
from schedule_import import RUZ_SCHEDULE_URL
from schedule_import import parse_spbstu_schedule


def main() -> None:
    init_database()
    tasks = parse_spbstu_schedule(RUZ_SCHEDULE_URL)
    for item in tasks:
        upsert_external_task(item)

    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(id) FROM tasks WHERE external_source = ?",
            ("spbstu-ruz",),
        ).fetchone()[0]

    print(f"Imported from page: {len(tasks)}")
    print(f"Stored university tasks: {total}")


if __name__ == "__main__":
    main()
