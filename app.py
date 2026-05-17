from __future__ import annotations

import re
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from database import cancel_regular_task_occurrence
from database import create_global_goal
from database import create_regular_task
from database import create_task
from database import create_task_group
from database import delete_global_goal
from database import delete_regular_task
from database import delete_task
from database import delete_task_group
from database import get_events_for_date as get_database_events_for_date
from database import get_global_goals
from database import get_group_color_palette
from database import get_reminders_for_date as get_database_reminders_for_date
from database import get_task_groups
from database import init_database
from database import reorder_task_groups
from database import update_global_goal
from database import update_regular_task
from database import update_task
from database import update_task_done
from database import update_task_group
from database import upsert_external_task
from database import upsert_regular_task_exception
from schedule_import import RUZ_SCHEDULE_URL
from schedule_import import parse_spbstu_schedule

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "soft-blue-planner-local-secret")

AUTH_LOGIN = "shpull"
AUTH_PASSWORD = "1234"


@app.context_processor
def inject_static_version() -> dict[str, int]:
    static_root = Path(app.static_folder or "")
    css_paths = [
        static_root / "css" / "style.css",
        static_root / "css" / "auth.css",
    ]
    try:
        version = max(int(path.stat().st_mtime) for path in css_paths)
    except OSError:
        version = 0
    return {"static_version": version}


@app.before_request
def require_login():
    allowed_endpoints = {"health", "login", "static"}
    if request.endpoint in allowed_endpoints or session.get("is_authenticated"):
        return None

    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Нужна авторизация."}), 401

    return redirect(url_for("login", next=request.full_path if request.query_string else request.path))

# База создаётся автоматически при запуске проекта.
# Файл базы: planner.db в корне проекта.
init_database()


WEEKDAY_LABELS = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
WEEKDAY_FULL_LABELS = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]
MONTH_LABELS = {
    1: "янв",
    2: "фев",
    3: "мар",
    4: "апр",
    5: "май",
    6: "июн",
    7: "июл",
    8: "авг",
    9: "сен",
    10: "окт",
    11: "ноя",
    12: "дек",
}
MONTH_FULL_LABELS = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь",
}

# Пока календарь показывает фиксированный промежуток — 3 недели.
# Позже это можно будет заменить на текущую неделю/месяц или выбор диапазона.
CALENDAR_DAYS_BEFORE = 7
CALENDAR_DAYS_AFTER = 35
TOTAL_CALENDAR_DAYS = CALENDAR_DAYS_BEFORE + CALENDAR_DAYS_AFTER
UNIVERSITY_IMPORT_WEEKS = 5

ART_CYCLE = [
    "wave",
    "flowers",
    "sprout",
    "mountains",
    "lotus",
    "paper",
    "whale",
]

CALENDAR_RANDOM_IMAGES = [
    f"{prefix} ({number}).png"
    for prefix in (1, 2)
    for number in range(1, 11)
]

TIME_RE = re.compile(r"^\d{2}:\d{2}$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
PRIORITIES = {"low", "normal", "high"}


def get_current_date() -> date:
    return date.today()


def get_calendar_start(current_date: date | None = None) -> date:
    current_date = current_date or get_current_date()
    current_week_start = current_date - timedelta(days=current_date.weekday())
    return current_week_start - timedelta(days=CALENDAR_DAYS_BEFORE)


def get_requested_calendar_start() -> date:
    raw_start = request.args.get("start", "").strip()
    if not raw_start:
        return get_calendar_start()
    start_date = date.fromisoformat(raw_start)
    return start_date - timedelta(days=start_date.weekday())


def build_today(current_date: date) -> dict[str, str]:
    return {
        "weekday": WEEKDAY_FULL_LABELS[current_date.weekday()],
        "day": str(current_date.day),
        "month": MONTH_FULL_LABELS[current_date.month],
        "year": str(current_date.year),
    }


def get_event_start_minutes(event_item: dict[str, Any]) -> int:
    start_time = event_item.get("start_time") or event_item["time"].split("—", 1)[0]
    hours, minutes = start_time.split(":")
    return int(hours) * 60 + int(minutes)


def get_events_for_date(current_date: date) -> list[dict[str, Any]]:
    day_events = get_database_events_for_date(current_date)
    return sorted(day_events, key=get_event_start_minutes)


def get_reminders_for_date(current_date: date) -> list[dict[str, Any]]:
    return get_database_reminders_for_date(current_date)


def build_day_payload(
    current_day: date,
    index: int,
    selected_date: date | None = None,
    today_date: date | None = None,
) -> dict[str, Any]:
    """Готовит день календаря для HTML и JavaScript."""
    selected_date = selected_date or get_current_date()
    today_date = today_date or get_current_date()

    return {
        "index": index,
        "iso": current_day.isoformat(),
        "weekday": WEEKDAY_LABELS[current_day.weekday()],
        "weekday_number": current_day.weekday(),
        "weekday_full": WEEKDAY_FULL_LABELS[current_day.weekday()],
        "day": str(current_day.day),
        "month": MONTH_LABELS[current_day.month],
        "month_full": MONTH_FULL_LABELS[current_day.month],
        "year": str(current_day.year),
        "is_today": current_day == today_date,
        "is_selected": current_day == selected_date,
        "art": ART_CYCLE[index % len(ART_CYCLE)],
        "random_art": f"/static/images/calendar-random-picture/{CALENDAR_RANDOM_IMAGES[current_day.toordinal() % len(CALENDAR_RANDOM_IMAGES)]}",
        "events": get_events_for_date(current_day),
        "reminders": get_reminders_for_date(current_day),
    }


def build_days(
    total_days: int = TOTAL_CALENDAR_DAYS,
    selected_date: date | None = None,
    start_date: date | None = None,
) -> list[dict[str, Any]]:
    days = []
    today_date = get_current_date()
    selected_date = selected_date or today_date
    start_date = start_date or get_calendar_start(today_date)

    for index in range(total_days):
        current_day = start_date + timedelta(days=index)
        days.append(build_day_payload(current_day, index, selected_date, today_date))

    return days


def get_json_payload() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Нужно отправить JSON-объект.")
    return payload


def require_text(payload: dict[str, Any], field: str, label: str) -> str:
    value = str(payload.get(field, "")).strip()
    if not value:
        raise ValueError(f"Поле «{label}» обязательно.")
    return value


def require_date(payload: dict[str, Any], field: str, label: str) -> str:
    value = require_text(payload, field, label)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Поле «{label}» должно быть датой в формате YYYY-MM-DD.") from exc
    return value


def require_time(payload: dict[str, Any], field: str, label: str) -> str:
    value = require_text(payload, field, label)
    if not TIME_RE.match(value):
        raise ValueError(f"Поле «{label}» должно быть временем в формате HH:MM.")
    hours, minutes = map(int, value.split(":"))
    if hours > 23 or minutes > 59:
        raise ValueError(f"Поле «{label}» содержит некорректное время.")
    return value


def require_weekday(payload: dict[str, Any]) -> int:
    try:
        weekday = int(payload.get("weekday"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Выберите день недели для регулярной задачи.") from exc
    if weekday < 0 or weekday > 6:
        raise ValueError("День недели должен быть от 0 до 6.")
    return weekday


def require_int(payload: dict[str, Any], field: str, label: str) -> int:
    try:
        value = int(payload.get(field, 1))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Поле «{label}» должно быть целым числом.") from exc

    return value


def normalise_reminder_days(payload: dict[str, Any]) -> list[int]:
    raw_value = payload.get("reminder_days", [])
    if isinstance(raw_value, str):
        parts = [part.strip() for part in raw_value.replace(";", ",").split(",")]
    elif isinstance(raw_value, list):
        parts = raw_value
    else:
        raise ValueError("Поле «напоминания» должно быть списком дней или строкой через запятую.")

    reminder_days: set[int] = set()
    for part in parts:
        if part in ("", None):
            continue
        try:
            value = int(part)
        except (TypeError, ValueError) as exc:
            raise ValueError("Напоминания указываются целыми числами: например 1, 3, 7.") from exc
        if value < 0:
            raise ValueError("Напоминания не могут быть отрицательными.")
        reminder_days.add(value)

    return sorted(reminder_days)


def normalise_group_payload(payload: dict[str, Any]) -> dict[str, str]:
    group_name = str(payload.get("group_name", "")).strip()
    group_color = str(payload.get("group_color", "#789dbb")).strip() or "#789dbb"
    if group_name and not COLOR_RE.match(group_color):
        raise ValueError("Цвет группы должен быть в формате #789dbb.")
    return {"group_name": group_name, "group_color": group_color}


def normalise_task_group_payload(payload: dict[str, Any]) -> dict[str, str]:
    name = require_text(payload, "name", "название блока")
    color = str(payload.get("color", "#789dbb")).strip() or "#789dbb"
    if not COLOR_RE.match(color):
        raise ValueError("Цвет блока должен быть в формате #789dbb.")
    return {"name": name, "color": color}


def normalise_priority(payload: dict[str, Any]) -> str:
    priority = str(payload.get("priority", "normal")).strip() or "normal"
    if priority not in PRIORITIES:
        raise ValueError("Приоритет должен быть low, normal или high.")
    return priority


def normalise_task_payload(payload: dict[str, Any]) -> dict[str, Any]:
    start_time = require_time(payload, "start_time", "начало")
    end_time = require_time(payload, "end_time", "конец")
    if end_time <= start_time:
        raise ValueError("Время окончания должно быть позже времени начала.")

    group_data = normalise_group_payload(payload)
    progress_goal_id = None
    if payload.get("progress_goal_id") not in ("", None):
        progress_goal_id = require_int(payload, "progress_goal_id", "цель")
        if progress_goal_id < 1:
            raise ValueError("Цель должна быть выбрана из списка.")

    return {
        "title": require_text(payload, "title", "название"),
        "date": require_date(payload, "date", "дата"),
        "start_time": start_time,
        "end_time": end_time,
        "note": str(payload.get("note", "")).strip(),
        "reminder_days": normalise_reminder_days(payload),
        "priority": normalise_priority(payload),
        "progress_goal_id": progress_goal_id,
        "contributes_progress": bool(payload.get("contributes_progress")) and progress_goal_id is not None,
        **group_data,
    }


def normalise_goal_payload(payload: dict[str, Any]) -> dict[str, Any]:
    period = str(payload.get("period", "month")).strip() or "month"
    if period not in {"week", "month", "season", "year", "other"}:
        raise ValueError("Период цели должен быть week, month, season, year или other.")
    target_date = None
    if period == "other" and payload.get("target_date") not in ("", None):
        target_date = require_date(payload, "target_date", "конкретная дата")
    return {
        "title": require_text(payload, "title", "название"),
        "period": period,
        "target_date": target_date,
        "description": str(payload.get("description", "")).strip(),
        "color": str(payload.get("color", "#789dbb")).strip() or "#789dbb",
    }


def normalise_regular_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = normalise_task_payload(payload)
    data["weekday"] = require_weekday(payload)
    data["start_date"] = require_date(payload, "start_date", "дата начала серии")
    data["counter_label"] = str(payload.get("counter_label", "раз")).strip() or "раз"
    data["counter_start"] = require_int(payload, "counter_start", "начало отсчёта")
    return data


def success_response(message: str = "Готово"):
    return jsonify({"ok": True, "message": message})


def error_response(error: Exception, status: int = 400):
    return jsonify({"ok": False, "error": str(error)}), status


def get_safe_next_url() -> str:
    next_url = request.args.get("next", "")
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return url_for("index")


@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/")
def index():
    current_date = get_current_date()
    week_days = build_days(selected_date=current_date)
    selected_day = next((day for day in week_days if day["is_selected"]), week_days[0])
    global_goals = get_global_goals()
    default_progress = global_goals[0]["progress"] if global_goals else 0

    return render_template(
        "index.html",
        today=build_today(current_date),
        selected_day=selected_day,
        today_events=selected_day["events"],
        week_days=week_days,
        progress=default_progress,
        weekday_full_labels=WEEKDAY_FULL_LABELS,
        task_groups=get_task_groups(),
        global_goals=global_goals,
        group_color_palette=get_group_color_palette(),
        schedule_url=RUZ_SCHEDULE_URL,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        login_value = request.form.get("login", "").strip()
        password_value = request.form.get("password", "")

        if login_value == AUTH_LOGIN and password_value == AUTH_PASSWORD:
            session.clear()
            session["is_authenticated"] = True
            return redirect(get_safe_next_url())

        error = "Неверный логин или пароль."

    return render_template("auth/login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/api/calendar")
def api_calendar():
    try:
        start_date = get_requested_calendar_start()
    except ValueError:
        return jsonify({"error": "Некорректная дата начала календаря."}), 400

    return jsonify({"days": build_days(start_date=start_date), "start": start_date.isoformat()})


@app.route("/api/day/<iso_date>")
def api_day(iso_date):
    try:
        current_day = date.fromisoformat(iso_date)
    except ValueError:
        return jsonify({"error": "Некорректная дата. Используйте формат YYYY-MM-DD."}), 400

    today_date = get_current_date()
    index = (current_day - get_calendar_start(today_date)).days
    return jsonify(build_day_payload(current_day, index, current_day, today_date))


@app.route("/api/task-groups")
def api_task_groups():
    return jsonify({"groups": get_task_groups()})


@app.route("/api/task-groups", methods=["POST"])
def api_create_task_group():
    try:
        create_task_group(normalise_task_group_payload(get_json_payload()))
    except ValueError as exc:
        return error_response(exc)
    return success_response("Блок добавлен.")


@app.route("/api/task-groups/<int:group_id>", methods=["PATCH"])
def api_update_task_group(group_id: int):
    try:
        update_task_group(group_id, normalise_task_group_payload(get_json_payload()))
    except ValueError as exc:
        return error_response(exc)
    return success_response("Блок обновлён.")


@app.route("/api/task-groups/<int:group_id>", methods=["DELETE"])
def api_delete_task_group(group_id: int):
    try:
        delete_task_group(group_id)
    except ValueError as exc:
        return error_response(exc, status=404)
    return success_response("Блок удалён.")


@app.route("/api/task-groups/reorder", methods=["PATCH"])
def api_reorder_task_groups():
    try:
        payload = get_json_payload()
        ids = payload.get("ids")
        if not isinstance(ids, list):
            raise ValueError("Нужно передать список id блоков.")
        reorder_task_groups([int(group_id) for group_id in ids])
    except ValueError as exc:
        return error_response(exc)
    return success_response("Порядок блоков сохранён.")


@app.route("/api/global-goals")
def api_global_goals():
    return jsonify({"goals": get_global_goals()})


@app.route("/api/global-goals", methods=["POST"])
def api_create_global_goal():
    try:
        create_global_goal(normalise_goal_payload(get_json_payload()))
    except ValueError as exc:
        return error_response(exc)
    return success_response("Цель добавлена.")


@app.route("/api/global-goals/<int:goal_id>", methods=["PATCH"])
def api_update_global_goal(goal_id: int):
    try:
        update_global_goal(goal_id, normalise_goal_payload(get_json_payload()))
    except ValueError as exc:
        return error_response(exc)
    return success_response("Цель обновлена.")


@app.route("/api/global-goals/<int:goal_id>", methods=["DELETE"])
def api_delete_global_goal(goal_id: int):
    try:
        delete_global_goal(goal_id)
    except ValueError as exc:
        return error_response(exc, status=404)
    return success_response("Цель удалена.")


@app.route("/api/university-schedule/import", methods=["POST"])
def api_import_university_schedule():
    try:
        payload = get_json_payload()
        url = str(payload.get("url") or RUZ_SCHEDULE_URL).strip()
        start_value = str(payload.get("start_date") or get_current_date().isoformat())
        import_start = date.fromisoformat(start_value)
        import_start = import_start - timedelta(days=import_start.weekday())
        weeks = int(payload.get("weeks") or UNIVERSITY_IMPORT_WEEKS)
        if weeks < 1 or weeks > 12:
            raise ValueError("Можно импортировать от 1 до 12 недель за раз.")

        imported = 0
        for week_index in range(weeks):
            week_start = import_start + timedelta(days=week_index * 7)
            for item in parse_spbstu_schedule(url, week_start):
                upsert_external_task(item)
                imported += 1
    except Exception as exc:
        return error_response(exc)

    return jsonify({"ok": True, "message": f"Импортировано занятий: {imported}.", "imported": imported})


@app.route("/api/tasks", methods=["POST"])
def api_create_task():
    try:
        data = normalise_task_payload(get_json_payload())
        create_task(data)
    except ValueError as exc:
        return error_response(exc)
    return success_response("Задача добавлена.")


@app.route("/api/tasks/<int:task_id>", methods=["PATCH"])
def api_update_task(task_id: int):
    try:
        data = normalise_task_payload(get_json_payload())
        update_task(task_id, data)
    except ValueError as exc:
        return error_response(exc)
    return success_response("Задача обновлена.")


@app.route("/api/tasks/<int:task_id>/done", methods=["PATCH"])
def api_update_task_done(task_id: int):
    try:
        payload = get_json_payload()
        update_task_done(task_id, bool(payload.get("is_done")))
    except ValueError as exc:
        return error_response(exc)
    return success_response("Статус задачи сохранён.")


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def api_delete_task(task_id: int):
    try:
        delete_task(task_id)
    except ValueError as exc:
        return error_response(exc, status=404)
    return success_response("Задача удалена.")


@app.route("/api/regular-tasks", methods=["POST"])
def api_create_regular_task():
    try:
        data = normalise_regular_payload(get_json_payload())
        create_regular_task(data)
    except ValueError as exc:
        return error_response(exc)
    return success_response("Регулярная задача добавлена.")


@app.route("/api/regular-tasks/<int:regular_task_id>", methods=["PATCH"])
def api_update_regular_task(regular_task_id: int):
    try:
        data = normalise_regular_payload(get_json_payload())
        update_regular_task(regular_task_id, data)
    except ValueError as exc:
        return error_response(exc)
    return success_response("Регулярная серия обновлена.")


@app.route("/api/regular-tasks/<int:regular_task_id>", methods=["DELETE"])
def api_delete_regular_task(regular_task_id: int):
    try:
        delete_regular_task(regular_task_id)
    except ValueError as exc:
        return error_response(exc, status=404)
    return success_response("Регулярная серия удалена.")


@app.route("/api/regular-occurrences/<int:regular_task_id>/<iso_date>", methods=["PATCH"])
def api_update_regular_occurrence(regular_task_id: int, iso_date: str):
    try:
        date.fromisoformat(iso_date)
        data = normalise_task_payload(get_json_payload())
        upsert_regular_task_exception(regular_task_id, iso_date, data, status="changed")
    except ValueError as exc:
        return error_response(exc)
    return success_response("Одно занятие обновлено.")


@app.route("/api/regular-occurrences/<int:regular_task_id>/<iso_date>", methods=["DELETE"])
def api_delete_regular_occurrence(regular_task_id: int, iso_date: str):
    try:
        date.fromisoformat(iso_date)
        cancel_regular_task_occurrence(regular_task_id, iso_date)
    except ValueError as exc:
        return error_response(exc)
    return success_response("Одно занятие отменено.")


if __name__ == "__main__":
    app.run(debug=True)
