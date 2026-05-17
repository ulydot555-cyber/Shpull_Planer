from __future__ import annotations

import json
import re
from datetime import date
from html import unescape
from typing import Any
from urllib.request import Request, urlopen


RUZ_SCHEDULE_URL = "https://ruz.spbstu.ru/faculty/125/groups/42785?date=2026-5-11"

LESSON_GROUP = {
    "name": "Учёба",
    "color": "#789dbb",
    "priority": "normal",
}
SESSION_GROUP = {
    "name": "Сессия",
    "color": "#b8848f",
    "priority": "high",
}


def build_schedule_url(url: str, week_start: date | None = None) -> str:
    if week_start is None:
        return url

    base_url = url.split("?", 1)[0]
    return f"{base_url}?date={week_start.year}-{week_start.month}-{week_start.day}"


def fetch_schedule_html(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 planner schedule importer",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=20) as response:
        encoding = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(encoding, errors="replace")


def extract_initial_state(html: str) -> dict[str, Any]:
    match = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*</script>", html, re.S)
    if match is None:
        raise ValueError("Не удалось найти данные расписания на странице Политеха.")

    return json.loads(match.group(1))


def classify_lesson(lesson: dict[str, Any]) -> dict[str, str]:
    lesson_type = (lesson.get("typeObj") or {}).get("name", "")
    subject = lesson.get("subject", "")
    text = f"{lesson_type} {subject}".lower()
    session_markers = ("консульта", "зач", "экзам", "курсов", "защит")
    return SESSION_GROUP if any(marker in text for marker in session_markers) else LESSON_GROUP


def format_note(lesson: dict[str, Any]) -> str:
    details = []
    lesson_type = (lesson.get("typeObj") or {}).get("name")
    if lesson_type:
        details.append(lesson_type)

    additional_info = lesson.get("additional_info")
    if additional_info:
        details.append(additional_info)

    teachers = [
        teacher.get("full_name", "").strip()
        for teacher in lesson.get("teachers") or []
        if teacher.get("full_name")
    ]
    if teachers:
        details.append("Преподаватель: " + ", ".join(teachers))

    places = []
    for auditorium in lesson.get("auditories") or []:
        building = (auditorium.get("building") or {}).get("name", "")
        room = auditorium.get("name", "")
        place = ", ".join(part for part in (building, f"ауд. {room}" if room else "") if part)
        if place:
            places.append(place)
    if places:
        details.append("Место: " + ", ".join(places))

    lms_url = lesson.get("lms_url")
    if lms_url:
        details.append("СДО: " + lms_url)

    return "\n".join(unescape(item) for item in details)


def build_task_payload(day: dict[str, Any], lesson: dict[str, Any], group_id: int) -> dict[str, Any]:
    group = classify_lesson(lesson)
    lesson_type = (lesson.get("typeObj") or {}).get("abbr") or (lesson.get("typeObj") or {}).get("name")
    title = lesson.get("subject") or "Занятие"
    if lesson_type:
        title = f"{title} · {lesson_type}"

    external_uid = "|".join(
        [
            str(group_id),
            str(day["date"]),
            str(lesson.get("time_start")),
            str(lesson.get("time_end")),
            str(lesson.get("subject")),
            str((lesson.get("typeObj") or {}).get("id", "")),
        ]
    )

    return {
        "title": title,
        "date": day["date"],
        "start_time": lesson["time_start"],
        "end_time": lesson["time_end"],
        "note": format_note(lesson),
        "reminder_days": [],
        "group_name": group["name"],
        "group_color": group["color"],
        "priority": group["priority"],
        "external_source": "spbstu-ruz",
        "external_uid": external_uid,
    }


def parse_spbstu_schedule(
    url: str = RUZ_SCHEDULE_URL,
    week_start: date | None = None,
) -> list[dict[str, Any]]:
    html = fetch_schedule_html(build_schedule_url(url, week_start))
    state = extract_initial_state(html)
    lessons_state = state.get("lessons", {})
    group_id = int((lessons_state.get("group") or {}).get("id") or 0)
    days_by_group = lessons_state.get("data") or {}
    days = days_by_group.get(str(group_id)) or []

    tasks = []
    for day in days:
        date.fromisoformat(day["date"])
        for lesson in day.get("lessons") or []:
            if not lesson.get("time_start") or not lesson.get("time_end"):
                continue
            tasks.append(build_task_payload(day, lesson, group_id))

    return tasks
