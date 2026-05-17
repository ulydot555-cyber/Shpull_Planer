from __future__ import annotations

import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "planner.db"
GROUP_COLOR_PALETTE = (
    "#789dbb",
    "#9fb7cc",
    "#5f86a6",
    "#8aa899",
    "#b7a87a",
    "#d7a66f",
    "#c98f83",
    "#b8848f",
    "#a794c7",
    "#7f9fc9",
    "#6fa6a2",
    "#a7b778",
    "#d0b08f",
    "#9d8a78",
    "#6f7f8f",
)

# Эти даты нужны только для первичного наполнения базы тестовыми данными.
SEED_START_DATE = date(2025, 6, 23)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database(seed_demo: bool = False) -> None:
    """Создаёт таблицы и один раз добавляет стартовые данные."""
    with get_connection() as conn:
        create_schema(conn)
        if seed_demo:
            seed_database_if_empty(conn)


def reset_database(seed_demo: bool = False) -> None:
    """Полностью пересоздаёт базу. Используется через init_db.py --reset."""
    with get_connection() as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS regular_task_exceptions;
            DROP TABLE IF EXISTS regular_tasks;
            DROP TABLE IF EXISTS tasks;
            DROP TABLE IF EXISTS global_goals;
            """
        )
        create_schema(conn)
        if seed_demo:
            seed_database_if_empty(conn)


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            note TEXT DEFAULT '',
            reminder_days TEXT NOT NULL DEFAULT '',
            group_id INTEGER,
            progress_goal_id INTEGER,
            contributes_progress INTEGER NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'normal',
            external_source TEXT,
            external_uid TEXT,
            is_done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES task_groups(id) ON DELETE SET NULL,
            FOREIGN KEY (progress_goal_id) REFERENCES global_goals(id) ON DELETE SET NULL,
            UNIQUE (external_source, external_uid)
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_date ON tasks(date);

        CREATE TABLE IF NOT EXISTS regular_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            start_date TEXT NOT NULL,
            counter_label TEXT NOT NULL DEFAULT 'раз',
            counter_start INTEGER NOT NULL DEFAULT 1,
            note TEXT DEFAULT '',
            reminder_days TEXT NOT NULL DEFAULT '',
            group_id INTEGER,
            priority TEXT NOT NULL DEFAULT 'normal',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES task_groups(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS task_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT NOT NULL DEFAULT '#789dbb',
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS global_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            period TEXT NOT NULL DEFAULT 'month',
            target_date TEXT,
            description TEXT DEFAULT '',
            color TEXT NOT NULL DEFAULT '#789dbb',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_regular_tasks_weekday ON regular_tasks(weekday);

        CREATE TABLE IF NOT EXISTS regular_task_exceptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            regular_task_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'changed',
            title_override TEXT,
            start_time_override TEXT,
            end_time_override TEXT,
            note_override TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (regular_task_id) REFERENCES regular_tasks(id) ON DELETE CASCADE,
            UNIQUE (regular_task_id, date)
        );

        CREATE INDEX IF NOT EXISTS idx_regular_task_exceptions_date
        ON regular_task_exceptions(date);
        """
    )
    migrate_schema(conn)


def migrate_schema(conn: sqlite3.Connection) -> None:
    task_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
    }
    regular_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(regular_tasks)").fetchall()
    }

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS task_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT NOT NULL DEFAULT '#789dbb',
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    group_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(task_groups)").fetchall()
    }
    if "sort_order" not in group_columns:
        conn.execute("ALTER TABLE task_groups ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")
        conn.execute("UPDATE task_groups SET sort_order = id WHERE sort_order = 0")

    for sort_order, (name, color) in enumerate(
        (
            ("Учёба", "#789dbb"),
            ("Сессия", "#b8848f"),
        ),
        start=1,
    ):
        conn.execute(
            """
            INSERT INTO task_groups (name, color, sort_order)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO NOTHING
            """,
            (name, color, sort_order),
        )

    if "reminder_days" not in task_columns:
        conn.execute(
            "ALTER TABLE tasks "
            "ADD COLUMN reminder_days TEXT NOT NULL DEFAULT ''"
        )

    for column_name, column_sql in (
        ("group_id", "ADD COLUMN group_id INTEGER"),
        ("progress_goal_id", "ADD COLUMN progress_goal_id INTEGER"),
        ("contributes_progress", "ADD COLUMN contributes_progress INTEGER NOT NULL DEFAULT 0"),
        ("priority", "ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'"),
        ("external_source", "ADD COLUMN external_source TEXT"),
        ("external_uid", "ADD COLUMN external_uid TEXT"),
    ):
        if column_name not in task_columns:
            conn.execute(f"ALTER TABLE tasks {column_sql}")

    if "counter_start" not in regular_columns:
        conn.execute(
            "ALTER TABLE regular_tasks "
            "ADD COLUMN counter_start INTEGER NOT NULL DEFAULT 1"
        )

    if "reminder_days" not in regular_columns:
        conn.execute(
            "ALTER TABLE regular_tasks "
            "ADD COLUMN reminder_days TEXT NOT NULL DEFAULT ''"
        )

    for column_name, column_sql in (
        ("group_id", "ADD COLUMN group_id INTEGER"),
        ("priority", "ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'"),
    ):
        if column_name not in regular_columns:
            conn.execute(f"ALTER TABLE regular_tasks {column_sql}")

    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_external_uid
        ON tasks(external_source, external_uid)
        WHERE external_source IS NOT NULL AND external_uid IS NOT NULL
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS global_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            period TEXT NOT NULL DEFAULT 'month',
            target_date TEXT,
            description TEXT DEFAULT '',
            color TEXT NOT NULL DEFAULT '#789dbb',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    goal_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(global_goals)").fetchall()
    }
    if "target_date" not in goal_columns:
        conn.execute("ALTER TABLE global_goals ADD COLUMN target_date TEXT")

    goals_count = conn.execute("SELECT COUNT(*) FROM global_goals").fetchone()[0]
    if goals_count == 0:
        conn.executemany(
            """
            INSERT INTO global_goals (title, period, description, color)
            VALUES (?, ?, ?, ?)
            """,
            (
                ("Месяц без суеты", "month", "Собрать важные дела в спокойный, видимый прогресс.", "#789dbb"),
                ("Неделя фокуса", "week", "Отмечайте задачи звёздочкой, чтобы они двигали цель.", "#b8848f"),
            ),
        )


def seed_database_if_empty(conn: sqlite3.Connection) -> None:
    tasks_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    regular_count = conn.execute("SELECT COUNT(*) FROM regular_tasks").fetchone()[0]

    if tasks_count or regular_count:
        return

    seed_tasks(conn)
    seed_regular_tasks(conn)


def seed_tasks(conn: sqlite3.Connection) -> None:
    # Ключ — номер дня от SEED_START_DATE: 0 = 23 июня, 1 = 24 июня и т.д.
    one_time_events_by_day = {
        0: [
            ("08:30", "09:30", "Йога", "Коврик, вода, спокойная разминка."),
            ("11:00", "12:30", "Исследование", "Собрать идеи и выписать 3 главных вывода."),
            ("17:00", "18:00", "Звонок с родителями", "Обсудить планы на выходные."),
        ],
        1: [
            ("09:00", "10:30", "Рабочий блок", "Закрыть самые срочные задачи."),
            ("14:00", "16:00", "Рабочий блок", "Без мессенджеров, только фокус."),
            ("19:00", "20:00", "Чтение", "20 страниц без телефона."),
        ],
        2: [
            ("08:30", "09:30", "Йога", "Лёгкая практика, не перегружаться."),
            ("11:00", "12:30", "Фокус-блок", "Главная задача дня."),
            ("15:00", "16:00", "Учёба / курс", "Посмотреть урок и сделать конспект."),
            ("21:00", "21:30", "Рефлексия", "Записать, что получилось хорошо."),
        ],
        3: [
            ("10:00", "11:30", "Презентация проекта", "Проверить структуру и финальный слайд."),
            ("13:00", "14:00", "Подготовка материалов", "Собрать файлы в одну папку."),
            ("18:30", "19:30", "Прогулка", "Без наушников, просто проветриться."),
        ],
        4: [
            ("09:30", "11:00", "Учёба / курс", "Разобрать сложные места."),
            ("16:00", "17:00", "Личное время вечером", "Ничего не планировать поверх."),
            ("20:30", "21:00", "Дневник", "Короткая запись о дне."),
        ],
        5: [
            ("10:00", "11:30", "День для себя", "Медленное утро."),
            ("15:00", "16:30", "Природа и вдохновение", "Сделать пару фото для настроения."),
        ],
        6: [
            ("09:00", "10:00", "Рефлексия недели", "Итоги, благодарности, выводы."),
            ("14:00", "15:30", "Планирование следующей недели", "Выбрать 3 приоритета."),
        ],
        7: [
            ("08:30", "09:00", "Планирование", "Быстро расставить приоритеты."),
            ("10:00", "12:00", "Глубокая работа", "Один большой кусок проекта."),
            ("18:00", "19:00", "Спорт", "Лёгкая тренировка."),
        ],
        8: [
            ("09:30", "10:00", "Разбор задач", "Очистить список от лишнего."),
            ("12:00", "13:00", "Созвон", "Подготовить 3 вопроса заранее."),
            ("19:00", "20:00", "Чтение", "Продолжить текущую книгу."),
        ],
        9: [
            ("08:30", "09:30", "Йога", "Спина и дыхание."),
            ("11:00", "13:00", "Проект", "Собрать первую версию."),
            ("16:00", "17:00", "Учёба", "Повторить конспект."),
        ],
        10: [
            ("10:00", "11:00", "Материалы", "Проверить список нужного."),
            ("13:30", "15:00", "Рабочий блок", "Закрыть хвосты."),
            ("20:00", "20:30", "Дневник", "Что сегодня дало энергию?"),
        ],
        11: [
            ("09:00", "10:30", "Курс", "Практическая часть."),
            ("15:00", "16:00", "Домашние дела", "Мини-уборка без перфекционизма."),
            ("18:30", "19:30", "Прогулка", "Маршрут у воды или в парке."),
        ],
        12: [
            ("11:00", "12:00", "Лёгкая уборка", "Только поверхности и рабочее место."),
            ("16:00", "17:30", "Вдохновение", "Сохранить референсы."),
        ],
        13: [
            ("10:00", "11:00", "Итоги недели", "Что стоит повторить на следующей неделе?"),
            ("14:00", "15:00", "План на неделю", "Разложить по дням."),
        ],
        14: [
            ("08:30", "09:30", "Утренняя практика", "Мягкий старт дня."),
            ("11:00", "12:30", "Фокус-блок", "Одна главная задача."),
            ("17:30", "18:30", "Прогулка", "Без спешки."),
        ],
        15: [
            ("09:00", "10:00", "Почта и задачи", "Разобрать входящие."),
            ("13:00", "15:00", "Рабочий блок", "Сделать черновик."),
            ("19:30", "20:30", "Книга", "Читать для удовольствия."),
        ],
        16: [
            ("08:30", "09:30", "Йога", "Растяжка и дыхание."),
            ("12:00", "13:00", "Учёба", "Повторить материал."),
            ("18:00", "19:00", "Свободное время", "Ничего обязательного."),
        ],
        17: [
            ("10:00", "12:00", "Проект", "Подготовить чистовую версию."),
            ("15:00", "16:00", "Созвон", "Зафиксировать решения."),
            ("20:30", "21:00", "Рефлексия", "Что улучшить завтра?"),
        ],
        18: [
            ("09:30", "11:00", "Курс", "Практика и закрепление."),
            ("14:00", "15:00", "Планирование", "Обновить список целей."),
            ("18:00", "19:00", "Спорт", "Лёгкая нагрузка."),
        ],
        19: [
            ("10:00", "11:30", "День для себя", "Пауза и восстановление."),
            ("15:30", "16:30", "Творческий час", "Без оценки результата."),
        ],
        20: [
            ("09:30", "10:30", "Медленное утро", "Начать день спокойно."),
            ("13:00", "14:00", "Итоги трёх недель", "Посмотреть прогресс и выводы."),
        ],
    }

    rows = []
    for day_index, events in one_time_events_by_day.items():
        event_date = (SEED_START_DATE + timedelta(days=day_index)).isoformat()
        for start_time, end_time, title, note in events:
            rows.append((title, event_date, start_time, end_time, note, 0))

    conn.executemany(
        """
        INSERT INTO tasks (title, date, start_time, end_time, note, is_done)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def seed_regular_tasks(conn: sqlite3.Connection) -> None:
    rows = [
        (
            "Английский",
            1,
            "10:00",
            "11:00",
            "2025-06-03",
            "урок",
            1,
            "Повторить слова и подготовить 2 вопроса преподавателю.",
            1,
        ),
        (
            "Корейский",
            2,
            "18:00",
            "19:00",
            "2025-06-11",
            "занятие",
            1,
            "Повторить грамматику и новые слова перед уроком.",
            1,
        ),
    ]

    conn.executemany(
        """
        INSERT INTO regular_tasks
            (title, weekday, start_time, end_time, start_date, counter_label, counter_start, note, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def make_time_range(start_time: str, end_time: str) -> str:
    return f"{start_time}—{end_time}"


def encode_reminder_days(values: list[int] | None) -> str:
    if not values:
        return ""
    return ",".join(str(value) for value in sorted(set(int(item) for item in values)))


def decode_reminder_days(value: str | None) -> list[int]:
    if not value:
        return []

    result = []
    for part in value.split(","):
        part = part.strip()
        if part:
            result.append(int(part))

    return sorted(set(result))


def normalise_group_color(color: str | None) -> str:
    value = (color or "#789dbb").strip()
    if re.match(r"^#[0-9a-fA-F]{6}$", value):
        return value.lower()
    return "#789dbb"


def get_or_create_task_group(
    conn: sqlite3.Connection,
    name: str | None,
    color: str | None,
    update_existing: bool = True,
) -> int | None:
    clean_name = (name or "").strip()
    if not clean_name:
        return None

    clean_color = normalise_group_color(color)
    row = conn.execute("SELECT id FROM task_groups WHERE name = ?", (clean_name,)).fetchone()
    if row is not None:
        if update_existing:
            conn.execute(
                "UPDATE task_groups SET color = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (clean_color, row["id"]),
            )
        return int(row["id"])

    cursor = conn.execute(
        """
        INSERT INTO task_groups (name, color, sort_order)
        VALUES (?, ?, (SELECT COALESCE(MAX(sort_order), 0) + 1 FROM task_groups))
        """,
        (clean_name, clean_color),
    )
    return int(cursor.lastrowid)


def get_task_groups() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, color, sort_order FROM task_groups ORDER BY sort_order, id"
        ).fetchall()
    return [dict(row) for row in rows]


def create_task_group(data: dict[str, Any]) -> int:
    name = str(data.get("name", "")).strip()
    if not name:
        raise ValueError("Название блока обязательно.")

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO task_groups (name, color, sort_order)
            VALUES (?, ?, (SELECT COALESCE(MAX(sort_order), 0) + 1 FROM task_groups))
            ON CONFLICT(name) DO UPDATE SET
                color = excluded.color,
                updated_at = CURRENT_TIMESTAMP
            """,
            (name, normalise_group_color(data.get("color"))),
        )
        row = conn.execute("SELECT id FROM task_groups WHERE name = ?", (name,)).fetchone()
        return int(row["id"])


def update_task_group(group_id: int, data: dict[str, Any]) -> None:
    name = str(data.get("name", "")).strip()
    if not name:
        raise ValueError("Название блока обязательно.")

    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE task_groups
            SET name = ?,
                color = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (name, normalise_group_color(data.get("color")), group_id),
        )
        if cursor.rowcount == 0:
            raise ValueError("Блок не найден.")


def delete_task_group(group_id: int) -> None:
    with get_connection() as conn:
        exists = conn.execute("SELECT id FROM task_groups WHERE id = ?", (group_id,)).fetchone()
        if exists is None:
            raise ValueError("Блок не найден.")

        conn.execute("UPDATE tasks SET group_id = NULL, updated_at = CURRENT_TIMESTAMP WHERE group_id = ?", (group_id,))
        conn.execute("UPDATE regular_tasks SET group_id = NULL, updated_at = CURRENT_TIMESTAMP WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM task_groups WHERE id = ?", (group_id,))


def reorder_task_groups(group_ids: list[int]) -> None:
    clean_ids = [int(group_id) for group_id in group_ids]
    if len(clean_ids) != len(set(clean_ids)):
        raise ValueError("Порядок блоков содержит повторяющиеся id.")

    with get_connection() as conn:
        existing_ids = {
            int(row["id"])
            for row in conn.execute("SELECT id FROM task_groups").fetchall()
        }
        if set(clean_ids) != existing_ids:
            raise ValueError("Нужно передать порядок для всех блоков.")

        for sort_order, group_id in enumerate(clean_ids, start=1):
            conn.execute(
                """
                UPDATE task_groups
                SET sort_order = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (sort_order, group_id),
            )


def get_group_color_palette() -> list[str]:
    return list(GROUP_COLOR_PALETTE)


def get_global_goals() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                global_goals.*,
                COUNT(tasks.id) AS total_tasks,
                COALESCE(SUM(CASE WHEN tasks.is_done = 1 THEN 1 ELSE 0 END), 0) AS done_tasks
            FROM global_goals
            LEFT JOIN tasks
              ON tasks.progress_goal_id = global_goals.id
             AND tasks.contributes_progress = 1
            GROUP BY global_goals.id
            ORDER BY
                CASE global_goals.period
                    WHEN 'week' THEN 1
                    WHEN 'month' THEN 2
                    WHEN 'season' THEN 3
                    WHEN 'year' THEN 4
                    ELSE 5
                END,
                global_goals.created_at,
                global_goals.id
            """
        ).fetchall()

    goals = []
    for row in rows:
        item = dict(row)
        total = int(item["total_tasks"] or 0)
        done = int(item["done_tasks"] or 0)
        item["progress"] = round((done / total) * 100) if total else 0
        goals.append(item)
    return goals


def create_global_goal(data: dict[str, Any]) -> int:
    title = str(data.get("title", "")).strip()
    if not title:
        raise ValueError("Название цели обязательно.")

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO global_goals (title, period, target_date, description, color)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                title,
                str(data.get("period") or "month").strip() or "month",
                data.get("target_date"),
                str(data.get("description") or "").strip(),
                normalise_group_color(data.get("color")),
            ),
        )
        return int(cursor.lastrowid)


def update_global_goal(goal_id: int, data: dict[str, Any]) -> None:
    title = str(data.get("title", "")).strip()
    if not title:
        raise ValueError("Название цели обязательно.")

    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE global_goals
            SET title = ?,
                period = ?,
                target_date = ?,
                description = ?,
                color = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                title,
                str(data.get("period") or "month").strip() or "month",
                data.get("target_date"),
                str(data.get("description") or "").strip(),
                normalise_group_color(data.get("color")),
                goal_id,
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError("Цель не найдена.")


def delete_global_goal(goal_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE tasks
            SET progress_goal_id = NULL,
                contributes_progress = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE progress_goal_id = ?
            """,
            (goal_id,),
        )
        cursor = conn.execute("DELETE FROM global_goals WHERE id = ?", (goal_id,))
        if cursor.rowcount == 0:
            raise ValueError("Цель не найдена.")


def task_row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": f"task-{row['id']}",
        "database_id": row["id"],
        "source": "task",
        "date": row["date"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "time": make_time_range(row["start_time"], row["end_time"]),
        "title": row["title"],
        "note": row["note"] or "",
        "is_done": bool(row["is_done"]),
        "is_regular": False,
        "counter_label": None,
        "occurrence_number": None,
        "reminder_days": decode_reminder_days(row["reminder_days"]),
        "priority": row["priority"],
        "group_id": row["group_id"],
        "group_name": row["group_name"],
        "group_color": row["group_color"],
        "progress_goal_id": row["progress_goal_id"],
        "contributes_progress": bool(row["contributes_progress"]),
        "progress_goal_title": row["progress_goal_title"],
        "external_source": row["external_source"],
        "external_uid": row["external_uid"],
    }


def get_one_time_events_for_date(conn: sqlite3.Connection, current_date: date) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            tasks.*,
            task_groups.name AS group_name,
            task_groups.color AS group_color,
            global_goals.title AS progress_goal_title
        FROM tasks
        LEFT JOIN task_groups ON task_groups.id = tasks.group_id
        LEFT JOIN global_goals ON global_goals.id = tasks.progress_goal_id
        WHERE date = ?
        ORDER BY start_time, end_time, id
        """,
        (current_date.isoformat(),),
    ).fetchall()

    return [task_row_to_event(row) for row in rows]


def get_regular_occurrence_number(regular_task: sqlite3.Row, current_date: date) -> int | None:
    weekday = int(regular_task["weekday"])
    start_date = date.fromisoformat(regular_task["start_date"])
    days_until_first_occurrence = (weekday - start_date.weekday()) % 7
    first_occurrence_date = start_date + timedelta(days=days_until_first_occurrence)

    if current_date < first_occurrence_date:
        return None

    counter_start = int(regular_task["counter_start"])
    return ((current_date - first_occurrence_date).days // 7) + counter_start


def get_exception_for_regular_task(
    conn: sqlite3.Connection,
    regular_task_id: int,
    current_date: date,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT *
        FROM regular_task_exceptions
        WHERE regular_task_id = ? AND date = ?
        """,
        (regular_task_id, current_date.isoformat()),
    ).fetchone()


def choose_override(exception: sqlite3.Row | None, field_name: str, default_value: str) -> str:
    if exception is None:
        return default_value

    value = exception[field_name]
    return default_value if value is None else value


def regular_row_to_event(
    row: sqlite3.Row,
    current_date: date,
    occurrence_number: int,
    exception: sqlite3.Row | None,
) -> dict[str, Any] | None:
    if exception is not None and exception["status"] == "cancelled":
        return None

    title = choose_override(exception, "title_override", row["title"])
    start_time = choose_override(exception, "start_time_override", row["start_time"])
    end_time = choose_override(exception, "end_time_override", row["end_time"])
    note = choose_override(exception, "note_override", row["note"] or "")

    return {
        "id": f"regular-{row['id']}-{current_date.isoformat()}",
        "database_id": row["id"],
        "source": "regular",
        "date": current_date.isoformat(),
        "start_time": start_time,
        "end_time": end_time,
        "time": make_time_range(start_time, end_time),
        "title": title,
        "note": note,
        "is_done": False,
        "is_regular": True,
        "counter_label": row["counter_label"],
        "counter_start": row["counter_start"],
        "occurrence_number": occurrence_number,
        "reminder_days": decode_reminder_days(row["reminder_days"]),
        "priority": row["priority"],
        "group_id": row["group_id"],
        "group_name": row["group_name"],
        "group_color": row["group_color"],
        "progress_goal_id": None,
        "contributes_progress": False,
        "progress_goal_title": None,
        "weekday": row["weekday"],
        "series_start_date": row["start_date"],
        "exception_id": exception["id"] if exception is not None else None,
    }


def get_regular_events_for_date(conn: sqlite3.Connection, current_date: date) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT regular_tasks.*, task_groups.name AS group_name, task_groups.color AS group_color
        FROM regular_tasks
        LEFT JOIN task_groups ON task_groups.id = regular_tasks.group_id
        WHERE is_active = 1
          AND weekday = ?
          AND start_date <= ?
        ORDER BY start_time, end_time, id
        """,
        (current_date.weekday(), current_date.isoformat()),
    ).fetchall()

    result = []

    for row in rows:
        occurrence_number = get_regular_occurrence_number(row, current_date)
        if occurrence_number is None:
            continue

        exception = get_exception_for_regular_task(conn, row["id"], current_date)
        event = regular_row_to_event(row, current_date, occurrence_number, exception)
        if event is not None:
            result.append(event)

    return result


def get_events_for_date(current_date: date) -> list[dict[str, Any]]:
    with get_connection() as conn:
        events = [
            *get_one_time_events_for_date(conn, current_date),
            *get_regular_events_for_date(conn, current_date),
        ]

    return sorted(events, key=lambda item: (item["start_time"], item["end_time"], item["title"]))


def reminder_from_event(event: dict[str, Any], reminder_date: date, days_before: int) -> dict[str, Any]:
    return {
        "id": f"reminder-{event['id']}-{days_before}",
        "event_id": event["id"],
        "source": event["source"],
        "database_id": event["database_id"],
        "title": event["title"],
        "date": event["date"],
        "reminder_date": reminder_date.isoformat(),
        "days_before": days_before,
        "time": event["time"],
        "start_time": event["start_time"],
        "end_time": event["end_time"],
        "is_regular": event["is_regular"],
        "counter_label": event.get("counter_label"),
        "occurrence_number": event.get("occurrence_number"),
    }


def get_one_time_reminders_for_date(conn: sqlite3.Connection, reminder_date: date) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            tasks.*,
            task_groups.name AS group_name,
            task_groups.color AS group_color,
            global_goals.title AS progress_goal_title
        FROM tasks
        LEFT JOIN task_groups ON task_groups.id = tasks.group_id
        LEFT JOIN global_goals ON global_goals.id = tasks.progress_goal_id
        WHERE date >= ?
          AND reminder_days != ''
        ORDER BY date, start_time, end_time, id
        """,
        (reminder_date.isoformat(),),
    ).fetchall()

    result = []
    for row in rows:
        event = task_row_to_event(row)
        days_before = (date.fromisoformat(event["date"]) - reminder_date).days
        if days_before in event["reminder_days"]:
            result.append(reminder_from_event(event, reminder_date, days_before))

    return result


def get_regular_reminders_for_date(conn: sqlite3.Connection, reminder_date: date) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT regular_tasks.*, task_groups.name AS group_name, task_groups.color AS group_color
        FROM regular_tasks
        LEFT JOIN task_groups ON task_groups.id = regular_tasks.group_id
        WHERE is_active = 1
          AND reminder_days != ''
        """,
    ).fetchall()

    result = []
    for row in rows:
        for days_before in decode_reminder_days(row["reminder_days"]):
            occurrence_date = reminder_date + timedelta(days=days_before)
            if occurrence_date.weekday() != int(row["weekday"]):
                continue
            if occurrence_date < date.fromisoformat(row["start_date"]):
                continue

            occurrence_number = get_regular_occurrence_number(row, occurrence_date)
            if occurrence_number is None:
                continue

            exception = get_exception_for_regular_task(conn, row["id"], occurrence_date)
            event = regular_row_to_event(row, occurrence_date, occurrence_number, exception)
            if event is not None:
                result.append(reminder_from_event(event, reminder_date, days_before))

    return result


def get_reminders_for_date(current_date: date) -> list[dict[str, Any]]:
    with get_connection() as conn:
        reminders = [
            *get_one_time_reminders_for_date(conn, current_date),
            *get_regular_reminders_for_date(conn, current_date),
        ]

    return sorted(reminders, key=lambda item: (item["date"], item["start_time"], item["title"]))


def create_task(data: dict[str, Any]) -> int:
    """Добавляет разовую задачу и возвращает её id."""
    with get_connection() as conn:
        group_id = get_or_create_task_group(conn, data.get("group_name"), data.get("group_color"))
        cursor = conn.execute(
            """
            INSERT INTO tasks
                (title, date, start_time, end_time, note, reminder_days, group_id, progress_goal_id, contributes_progress, priority, external_source, external_uid, is_done)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["title"],
                data["date"],
                data["start_time"],
                data["end_time"],
                data.get("note", ""),
                encode_reminder_days(data.get("reminder_days")),
                group_id,
                data.get("progress_goal_id") or None,
                int(bool(data.get("contributes_progress")) and bool(data.get("progress_goal_id"))),
                data.get("priority", "normal"),
                data.get("external_source"),
                data.get("external_uid"),
                int(bool(data.get("is_done", False))),
            ),
        )
        return int(cursor.lastrowid)


def update_task(task_id: int, data: dict[str, Any]) -> None:
    """Обновляет разовую задачу."""
    with get_connection() as conn:
        group_id = get_or_create_task_group(conn, data.get("group_name"), data.get("group_color"))
        cursor = conn.execute(
            """
            UPDATE tasks
            SET title = ?,
                date = ?,
                start_time = ?,
                end_time = ?,
                note = ?,
                reminder_days = ?,
                group_id = ?,
                progress_goal_id = ?,
                contributes_progress = ?,
                priority = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                data["title"],
                data["date"],
                data["start_time"],
                data["end_time"],
                data.get("note", ""),
                encode_reminder_days(data.get("reminder_days")),
                group_id,
                data.get("progress_goal_id") or None,
                int(bool(data.get("contributes_progress")) and bool(data.get("progress_goal_id"))),
                data.get("priority", "normal"),
                task_id,
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError("Задача не найдена.")


def update_task_done(task_id: int, is_done: bool) -> None:
    """Сохраняет состояние чекбокса для разовой задачи."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE tasks
            SET is_done = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (int(is_done), task_id),
        )
        if cursor.rowcount == 0:
            raise ValueError("Задача не найдена.")


def upsert_external_task(data: dict[str, Any]) -> int:
    with get_connection() as conn:
        group_id = get_or_create_task_group(
            conn,
            data.get("group_name"),
            data.get("group_color"),
            update_existing=False,
        )
        existing = conn.execute(
            "SELECT id FROM tasks WHERE external_source = ? AND external_uid = ?",
            (data["external_source"], data["external_uid"]),
        ).fetchone()

        if existing is not None:
            conn.execute(
                """
                UPDATE tasks
                SET title = ?,
                    date = ?,
                    start_time = ?,
                    end_time = ?,
                    note = ?,
                    reminder_days = ?,
                    group_id = ?,
                    progress_goal_id = ?,
                    contributes_progress = ?,
                    priority = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    data["title"],
                    data["date"],
                    data["start_time"],
                    data["end_time"],
                    data.get("note", ""),
                    encode_reminder_days(data.get("reminder_days")),
                    group_id,
                    data.get("progress_goal_id") or None,
                    int(bool(data.get("contributes_progress")) and bool(data.get("progress_goal_id"))),
                    data.get("priority", "normal"),
                    existing["id"],
                ),
            )
            return int(existing["id"])

        cursor = conn.execute(
            """
            INSERT INTO tasks
                (title, date, start_time, end_time, note, reminder_days, group_id, progress_goal_id, contributes_progress, priority, external_source, external_uid, is_done)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                data["title"],
                data["date"],
                data["start_time"],
                data["end_time"],
                data.get("note", ""),
                encode_reminder_days(data.get("reminder_days")),
                group_id,
                data.get("progress_goal_id") or None,
                int(bool(data.get("contributes_progress")) and bool(data.get("progress_goal_id"))),
                data.get("priority", "normal"),
                data["external_source"],
                data["external_uid"],
            ),
        )
        return int(cursor.lastrowid)


def delete_task(task_id: int) -> None:
    """Удаляет разовую задачу."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        if cursor.rowcount == 0:
            raise ValueError("Задача не найдена.")


def create_regular_task(data: dict[str, Any]) -> int:
    """Создаёт регулярную задачу и возвращает id серии."""
    with get_connection() as conn:
        group_id = get_or_create_task_group(conn, data.get("group_name"), data.get("group_color"))
        cursor = conn.execute(
            """
            INSERT INTO regular_tasks
                (title, weekday, start_time, end_time, start_date, counter_label, counter_start, note, reminder_days, group_id, priority, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                data["title"],
                int(data["weekday"]),
                data["start_time"],
                data["end_time"],
                data["start_date"],
                data.get("counter_label") or "раз",
                int(data.get("counter_start", 1)),
                data.get("note", ""),
                encode_reminder_days(data.get("reminder_days")),
                group_id,
                data.get("priority", "normal"),
            ),
        )
        return int(cursor.lastrowid)


def update_regular_task(regular_task_id: int, data: dict[str, Any]) -> None:
    """Обновляет всю регулярную серию."""
    with get_connection() as conn:
        group_id = get_or_create_task_group(conn, data.get("group_name"), data.get("group_color"))
        cursor = conn.execute(
            """
            UPDATE regular_tasks
            SET title = ?,
                weekday = ?,
                start_time = ?,
                end_time = ?,
                start_date = ?,
                counter_label = ?,
                counter_start = ?,
                note = ?,
                reminder_days = ?,
                group_id = ?,
                priority = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                data["title"],
                int(data["weekday"]),
                data["start_time"],
                data["end_time"],
                data["start_date"],
                data.get("counter_label") or "раз",
                int(data.get("counter_start", 1)),
                data.get("note", ""),
                encode_reminder_days(data.get("reminder_days")),
                group_id,
                data.get("priority", "normal"),
                regular_task_id,
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError("Регулярная задача не найдена.")


def delete_regular_task(regular_task_id: int) -> None:
    """Удаляет всю регулярную серию."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM regular_tasks WHERE id = ?", (regular_task_id,))
        if cursor.rowcount == 0:
            raise ValueError("Регулярная задача не найдена.")


def upsert_regular_task_exception(
    regular_task_id: int,
    occurrence_date: str,
    data: dict[str, Any],
    status: str = "changed",
) -> None:
    """Создаёт или обновляет исключение для одного экземпляра регулярной задачи."""
    with get_connection() as conn:
        exists = conn.execute(
            """
            SELECT id
            FROM regular_task_exceptions
            WHERE regular_task_id = ? AND date = ?
            """,
            (regular_task_id, occurrence_date),
        ).fetchone()

        values = (
            status,
            data.get("title"),
            data.get("start_time"),
            data.get("end_time"),
            data.get("note", ""),
            regular_task_id,
            occurrence_date,
        )

        if exists:
            conn.execute(
                """
                UPDATE regular_task_exceptions
                SET status = ?,
                    title_override = ?,
                    start_time_override = ?,
                    end_time_override = ?,
                    note_override = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE regular_task_id = ? AND date = ?
                """,
                values,
            )
        else:
            conn.execute(
                """
                INSERT INTO regular_task_exceptions
                    (status, title_override, start_time_override, end_time_override, note_override, regular_task_id, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )


def cancel_regular_task_occurrence(regular_task_id: int, occurrence_date: str) -> None:
    """Отменяет один экземпляр регулярной задачи."""
    # Поля override оставляем пустыми: для отменённого события они не нужны.
    upsert_regular_task_exception(
        regular_task_id,
        occurrence_date,
        {
            "title": None,
            "start_time": None,
            "end_time": None,
            "note": None,
        },
        status="cancelled",
    )
