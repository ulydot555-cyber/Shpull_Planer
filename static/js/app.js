const weekScroller = document.querySelector('#weekScroller');
const plannerDataScript = document.querySelector('#plannerData');
const goalsDataScript = document.querySelector('#goalsData');
const colorPaletteDataScript = document.querySelector('#colorPaletteData');
let plannerDays = plannerDataScript ? JSON.parse(plannerDataScript.textContent) : [];
let globalGoals = goalsDataScript ? JSON.parse(goalsDataScript.textContent) : [];
const colorPalette = colorPaletteDataScript ? JSON.parse(colorPaletteDataScript.textContent) : ['#789dbb'];
let taskGroups = [];
let calendarStartIso = plannerDays[0]?.iso || null;
let isShiftingCalendarWeeks = false;

let selectedDayIndex = plannerDays.findIndex((day) => day.is_selected);
if (selectedDayIndex < 0) selectedDayIndex = 0;

const modal = document.querySelector('#taskModal');
const taskForm = document.querySelector('#taskForm');
const formError = document.querySelector('#formError');
const modalTitle = document.querySelector('#taskModalTitle');
const formMode = document.querySelector('#formMode');
const formSource = document.querySelector('#formSource');
const formDatabaseId = document.querySelector('#formDatabaseId');
const formOriginalDate = document.querySelector('#formOriginalDate');
const taskTitle = document.querySelector('#taskTitle');
const taskDate = document.querySelector('#taskDate');
const taskType = document.querySelector('#taskType');
const taskStartTime = document.querySelector('#taskStartTime');
const taskEndTime = document.querySelector('#taskEndTime');
const taskNote = document.querySelector('#taskNote');
const taskReminderDays = document.querySelector('#taskReminderDays');
const taskGroupName = document.querySelector('#taskGroupName');
const taskGroupColor = document.querySelector('#taskGroupColor');
const taskPriority = document.querySelector('#taskPriority');
const taskProgressGoal = document.querySelector('#taskProgressGoal');
const taskContributesProgress = document.querySelector('#taskContributesProgress');
const regularScopeBlock = document.querySelector('#regularScopeBlock');
const regularFields = document.querySelector('#regularFields');
const regularWeekdays = document.querySelector('#regularWeekdays');
const regularStartDate = document.querySelector('#regularStartDate');
const regularCounterLabel = document.querySelector('#regularCounterLabel');
const regularCounterStartLabel = document.querySelector('#regularCounterStartLabel');
const regularCounterStart = document.querySelector('#regularCounterStart');
const formHint = document.querySelector('#formHint');
const weeklyFocusText = document.querySelector('#weeklyFocusText');
const monthProgressSelect = document.querySelector('#monthProgressSelect');
const goalForm = document.querySelector('#goalForm');
const goalFormId = document.querySelector('#goalFormId');
const goalTitle = document.querySelector('#goalTitle');
const goalPeriod = document.querySelector('#goalPeriod');
const goalTargetDateField = document.querySelector('#goalTargetDateField');
const goalTargetDate = document.querySelector('#goalTargetDate');
const goalDescription = document.querySelector('#goalDescription');
const goalColor = document.querySelector('#goalColor');
const groupModal = document.querySelector('#groupModal');
const groupForm = document.querySelector('#groupForm');
const groupFormId = document.querySelector('#groupFormId');
const groupModalTitle = document.querySelector('#groupModalTitle');
const groupName = document.querySelector('#groupName');
const groupColor = document.querySelector('#groupColor');
const groupFormError = document.querySelector('#groupFormError');

const WEEKDAY_FULL_LABELS = [
    'Понедельник',
    'Вторник',
    'Среда',
    'Четверг',
    'Пятница',
    'Суббота',
    'Воскресенье'
];

const WEEKLY_FOCUS_STORAGE_KEY = 'soft-blue-planner-weekly-focus';
const MONTH_PROGRESS_STORAGE_KEY = 'soft-blue-planner-month-progress-goal';
const PERIOD_LABELS = {
    week: 'Неделя',
    month: 'Месяц',
    season: 'Сезон',
    year: 'Год',
    other: 'План'
};

if (weeklyFocusText) {
    const savedFocus = localStorage.getItem(WEEKLY_FOCUS_STORAGE_KEY);
    if (savedFocus) {
        weeklyFocusText.textContent = savedFocus;
    }

    weeklyFocusText.addEventListener('input', () => {
        localStorage.setItem(WEEKLY_FOCUS_STORAGE_KEY, weeklyFocusText.textContent.trim());
    });

    weeklyFocusText.addEventListener('paste', (event) => {
        event.preventDefault();
        const text = event.clipboardData?.getData('text/plain') || '';
        document.execCommand('insertText', false, text);
    });
}

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function getSelectedDay() {
    return plannerDays[selectedDayIndex] ?? plannerDays[0];
}

function getDateWeekdayNumber(isoDate) {
    const date = new Date(`${isoDate}T12:00:00`);
    const jsDay = date.getDay();
    return jsDay === 0 ? 6 : jsDay - 1;
}

function getSelectedRegularWeekdays() {
    return [...(regularWeekdays?.querySelectorAll('input[name="weekdays"]:checked') || [])]
        .map((input) => Number(input.value))
        .filter((weekday) => Number.isInteger(weekday) && weekday >= 0 && weekday <= 6)
        .sort((a, b) => a - b);
}

function setSelectedRegularWeekdays(weekdays) {
    const selected = new Set((weekdays || []).map((weekday) => Number(weekday)));
    regularWeekdays?.querySelectorAll('input[name="weekdays"]').forEach((input) => {
        input.checked = selected.has(Number(input.value));
    });
}

function getFirstOccurrenceDate(startIso, weekdays) {
    const startDate = new Date(`${startIso}T12:00:00`);
    const selectedWeekdays = new Set((Array.isArray(weekdays) ? weekdays : [weekdays]).map((weekday) => Number(weekday)));
    for (let offset = 0; offset < 7; offset += 1) {
        const candidate = new Date(startDate);
        candidate.setDate(candidate.getDate() + offset);
        if (selectedWeekdays.has(getDateWeekdayNumber(candidate.toISOString().slice(0, 10)))) {
            return candidate;
        }
    }
    return startDate;
}

function getOccurrenceOffset(startIso, weekdays, occurrenceIso) {
    const selectedWeekdays = new Set((Array.isArray(weekdays) ? weekdays : [weekdays]).map((weekday) => Number(weekday)));
    const firstOccurrence = getFirstOccurrenceDate(startIso, [...selectedWeekdays]);
    const occurrenceDate = new Date(`${occurrenceIso}T12:00:00`);
    if (occurrenceDate < firstOccurrence) return 0;

    let offset = 0;
    const cursor = new Date(firstOccurrence);
    while (cursor < occurrenceDate) {
        if (selectedWeekdays.has(getDateWeekdayNumber(cursor.toISOString().slice(0, 10)))) {
            offset += 1;
        }
        cursor.setDate(cursor.getDate() + 1);
    }
    return offset;
}

function formatApiError(error) {
    if (!error) return 'Не получилось сохранить изменения.';
    return String(error);
}

async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        },
        ...options
    });

    let payload = {};
    try {
        payload = await response.json();
    } catch (error) {
        payload = {};
    }

    if (!response.ok || payload.ok === false) {
        throw new Error(formatApiError(payload.error));
    }

    return payload;
}

function getAllEvents() {
    return plannerDays.flatMap((day) => day.events || []);
}

function formatDateShort(isoDate) {
    const date = new Date(`${isoDate}T12:00:00`);
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

function formatDateLong(isoDate) {
    if (!isoDate) return '';
    const date = new Date(`${isoDate}T12:00:00`);
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
}

function findGoal(goalId) {
    return globalGoals.find((goal) => String(goal.id) === String(goalId));
}

function normaliseColorValue(value) {
    const color = String(value || '').trim().toLowerCase();
    return /^#[0-9a-f]{6}$/.test(color) ? color : (colorPalette[0] || '#789dbb');
}

function setColorValue(input, value) {
    if (!input) return;
    input.value = normaliseColorValue(value);
    updateColorPaletteSelection(input.id);
}

function updateColorPaletteSelection(inputId) {
    const input = document.querySelector(`#${CSS.escape(inputId)}`);
    const currentColor = normaliseColorValue(input?.value);
    document.querySelectorAll(`[data-color-palette="${CSS.escape(inputId)}"] .color-swatch`).forEach((button) => {
        button.classList.toggle('is-selected', normaliseColorValue(button.dataset.color) === currentColor);
    });
}

function renderColorPalettes() {
    document.querySelectorAll('[data-color-palette]').forEach((paletteElement) => {
        const inputId = paletteElement.dataset.colorPalette;
        paletteElement.innerHTML = colorPalette.map((color) => `
            <button class="color-swatch" type="button" data-color="${escapeHtml(color)}" style="--swatch-color: ${escapeHtml(color)}" aria-label="Цвет ${escapeHtml(color)}"></button>
        `).join('');
        updateColorPaletteSelection(inputId);
    });
}

document.addEventListener('click', (event) => {
    const swatch = event.target.closest('.color-swatch[data-color]');
    if (!swatch) return;
    const paletteElement = swatch.closest('[data-color-palette]');
    const input = paletteElement ? document.querySelector(`#${CSS.escape(paletteElement.dataset.colorPalette)}`) : null;
    setColorValue(input, swatch.dataset.color);
});

function updateGoalTargetDateVisibility() {
    if (!goalTargetDateField || !goalPeriod) return;
    const isOtherPeriod = goalPeriod.value === 'other';
    goalTargetDateField.hidden = !isOtherPeriod;
    if (!isOtherPeriod && goalTargetDate) goalTargetDate.value = '';
}

function readTaskGroupsFromDatalist() {
    taskGroups = [...document.querySelectorAll('#taskGroupsList option')].map((option) => ({
        id: option.dataset.id || '',
        name: option.value,
        color: option.dataset.color || '#789dbb'
    }));
}

function switchView(viewName) {
    document.querySelectorAll('[data-view]').forEach((view) => {
        const isActive = view.dataset.view === viewName;
        view.hidden = !isActive;
        view.classList.toggle('is-active', isActive);
    });

    document.querySelectorAll('[data-view-link]').forEach((link) => {
        link.classList.toggle('active', link.dataset.viewLink === viewName);
    });

    if (viewName === 'notes') renderNotesBoard();
    if (viewName === 'inspiration') renderGoals();
}

function updateGoalOptions() {
    const options = globalGoals
        .map((goal) => `<option value="${escapeHtml(goal.id)}">${escapeHtml(goal.title)}</option>`)
        .join('');

    if (taskProgressGoal) {
        const previous = taskProgressGoal.value;
        taskProgressGoal.innerHTML = `<option value="">Без цели</option>${options}`;
        taskProgressGoal.value = globalGoals.some((goal) => String(goal.id) === previous) ? previous : '';
    }

    if (monthProgressSelect) {
        const saved = localStorage.getItem(MONTH_PROGRESS_STORAGE_KEY);
        const previous = saved || monthProgressSelect.value || globalGoals[0]?.id || '';
        monthProgressSelect.innerHTML = globalGoals
            .map((goal) => `<option value="${escapeHtml(goal.id)}" data-progress="${escapeHtml(goal.progress)}">${escapeHtml(goal.title)}</option>`)
            .join('');
        monthProgressSelect.value = globalGoals.some((goal) => String(goal.id) === String(previous))
            ? String(previous)
            : String(globalGoals[0]?.id || '');
    }

    updateMonthProgress();
}

function updateMonthProgress() {
    const ring = document.querySelector('.progress-ring');
    const ringText = ring?.querySelector('span');
    const select = monthProgressSelect;
    const selectedGoal = findGoal(select?.value) || globalGoals[0];
    const progress = selectedGoal?.progress ?? 0;

    if (ring) ring.style.setProperty('--progress', progress);
    if (ringText) ringText.textContent = `${progress}%`;
    if (select?.value) localStorage.setItem(MONTH_PROGRESS_STORAGE_KEY, select.value);
}

async function refreshGoals() {
    const payload = await apiRequest('/api/global-goals');
    globalGoals = payload.goals || [];
    updateGoalOptions();
    renderGoals();
}

async function refreshTaskGroups() {
    const payload = await apiRequest('/api/task-groups');
    taskGroups = payload.groups || [];
    const datalist = document.querySelector('#taskGroupsList');
    if (datalist) {
        datalist.innerHTML = taskGroups
            .map((group) => `<option value="${escapeHtml(group.name)}" data-id="${escapeHtml(group.id)}" data-color="${escapeHtml(group.color)}"></option>`)
            .join('');
    }
    renderNotesBoard();
}

document.querySelectorAll('[data-scroll]').forEach((button) => {
    const target = document.querySelector(button.dataset.scrollTarget);

    button.addEventListener('click', () => {
        if (!target) return;
        const direction = button.dataset.scroll === 'next' ? 1 : -1;
        const maxScroll = target.scrollWidth - target.clientWidth;
        const atStart = target.scrollLeft <= 2;
        const atEnd = target.scrollLeft >= maxScroll - 2;

        if ((direction < 0 && atStart) || (direction > 0 && atEnd)) {
            shiftCalendarWeeks(direction);
            return;
        }

        target.scrollBy({ left: direction * target.clientWidth, behavior: 'smooth' });
    });
});

if (weekScroller) {
    weekScroller.addEventListener('wheel', (event) => {
        if (event.target.closest('.events-list')) return;
        if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;

        const maxScroll = weekScroller.scrollWidth - weekScroller.clientWidth;
        const atStart = weekScroller.scrollLeft <= 2;
        const atEnd = weekScroller.scrollLeft >= maxScroll - 2;
        if (event.deltaY < 0 && atStart) {
            event.preventDefault();
            shiftCalendarWeeks(-1, { scroller: weekScroller });
            return;
        }
        if (event.deltaY > 0 && atEnd) {
            event.preventDefault();
            shiftCalendarWeeks(1, { scroller: weekScroller });
            return;
        }

        event.preventDefault();
        weekScroller.scrollBy({
            left: event.deltaY,
            behavior: 'auto'
        });
    }, { passive: false });

    weekScroller.addEventListener('scroll', () => {
        handleCalendarEdgeScroll(weekScroller);
    }, { passive: true });
}

function renderEventActions(event = {}) {
    const goalTitle = event.progress_goal_title
        ? ` title="Двигает цель: ${escapeHtml(event.progress_goal_title)}"`
        : ' title="Добавить к прогрессу цели"';
    const progressButton = event.is_regular
        ? ''
        : `<button class="progress-star ${event.contributes_progress ? 'is-active' : ''}" type="button" data-event-action="progress" ${goalTitle}>${event.contributes_progress ? '★' : '☆'}</button>`;
    return `
        <div class="calendar-event-actions" aria-label="Действия с задачей">
            ${progressButton}
            <button type="button" data-event-action="edit" title="Редактировать">✎</button>
            <button type="button" data-event-action="delete" title="Удалить">×</button>
        </div>
    `;
}

function renderCalendarEvent(event) {
    const regularBadge = event.is_regular
        ? `<span class="regular-badge">${escapeHtml(event.counter_label)} ${escapeHtml(event.occurrence_number)}</span>`
        : '';

    return `
        <div class="event-card ${event.is_regular ? 'is-regular' : ''} priority-${escapeHtml(event.priority || 'normal')}" style="--group-color: ${escapeHtml(event.group_color || '#789dbb')}" data-event-id="${escapeHtml(event.id)}" data-event-source="${escapeHtml(event.source)}">
            ${renderEventActions(event)}
            <time>${escapeHtml(event.time)}</time>
            <p>${escapeHtml(event.title)}</p>
            ${event.group_name ? `<span class="group-badge">${escapeHtml(event.group_name)}</span>` : ''}
            ${regularBadge}
        </div>
    `;
}

function renderEventRow(event) {
    const regularBadge = event.is_regular
        ? `<em>${escapeHtml(event.counter_label)} ${escapeHtml(event.occurrence_number)}</em>`
        : '';

    const note = event.note
        ? `<small>${escapeHtml(event.note)}</small>`
        : '';

    const checked = event.is_done ? 'checked' : '';
    const disabled = event.is_regular ? 'disabled title="Для регулярных задач статус выполнения добавим позже"' : '';

    return `
        <div class="task-row daily-event-row ${event.is_regular ? 'is-regular' : ''} priority-${escapeHtml(event.priority || 'normal')}" style="--group-color: ${escapeHtml(event.group_color || '#789dbb')}" data-event-id="${escapeHtml(event.id)}" data-event-source="${escapeHtml(event.source)}">
            <input type="checkbox" ${checked} ${disabled} aria-label="Отметить задачу выполненной">
            <span class="daily-event-content">
                <span class="daily-event-meta">
                    <time>${escapeHtml(event.time)}</time>
                    ${event.group_name ? `<em class="group-badge">${escapeHtml(event.group_name)}</em>` : ''}
                    ${regularBadge}
                </span>
                <strong>${escapeHtml(event.title)}</strong>
                ${note}
            </span>
            <span class="row-actions" aria-label="Действия с задачей">
                ${!event.is_regular ? `<button class="progress-star ${event.contributes_progress ? 'is-active' : ''}" type="button" data-event-action="progress" title="${event.progress_goal_title ? `Двигает цель: ${escapeHtml(event.progress_goal_title)}` : 'Добавить к прогрессу цели'}">${event.contributes_progress ? '★' : '☆'}</button>` : ''}
                <button type="button" data-event-action="edit" title="Редактировать">✎</button>
                <button type="button" data-event-action="delete" title="Удалить">×</button>
            </span>
        </div>
    `;
}

function formatReminderDate(isoDate) {
    const date = new Date(`${isoDate}T12:00:00`);
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });
}

function formatDaysBefore(daysBefore) {
    if (daysBefore === 0) return 'сегодня';
    return `за ${daysBefore} дн.`;
}

function renderReminder(reminder) {
    const regularBadge = reminder.is_regular
        ? `<em>${escapeHtml(reminder.counter_label)} ${escapeHtml(reminder.occurrence_number)}</em>`
        : '';

    return `
        <p class="upcoming-reminder" data-event-id="${escapeHtml(reminder.event_id)}" data-event-source="${escapeHtml(reminder.source)}">
            <span>${escapeHtml(formatReminderDate(reminder.date))} · ${escapeHtml(reminder.time)} · ${escapeHtml(formatDaysBefore(reminder.days_before))}</span>
            <strong>${escapeHtml(reminder.title)}</strong>
            ${regularBadge}
        </p>
    `;
}

function renderNotesBoard() {
    const board = document.querySelector('#notesBoard');
    if (!board) return;

    const groups = new Map();
    taskGroups.forEach((group) => {
        groups.set(group.name, {
            id: group.id,
            name: group.name,
            color: group.color || '#789dbb',
            events: []
        });
    });

    getAllEvents().forEach((event) => {
        if (!event.group_name) return;
        const key = event.group_name;
        if (!groups.has(key)) {
            groups.set(key, {
                id: event.group_id || '',
                name: key,
                color: event.group_color || '#789dbb',
                events: []
            });
        }
        groups.get(key).events.push(event);
    });

    if (!groups.size) {
        board.innerHTML = '<p class="empty-state">Пока нет задач для заметок.</p>';
        return;
    }

    const renderedGroups = Array.from(groups.values());
    board.innerHTML = renderedGroups.map((group) => {
        const groupIndex = taskGroups.findIndex((item) => String(item.id) === String(group.id));
        const canMoveLeft = group.id && groupIndex > 0;
        const canMoveRight = group.id && groupIndex >= 0 && groupIndex < taskGroups.length - 1;
        return `
        <article class="note-column" style="--group-color: ${escapeHtml(group.color)}">
            <header>
                <div class="note-column-title">
                    <span class="note-color-dot"></span>
                    <h3>${escapeHtml(group.name)}</h3>
                </div>
                <div class="note-column-actions">
                    ${group.id ? `
                        <button type="button" data-note-move="${escapeHtml(group.id)}" data-note-direction="-1" title="Сдвинуть влево" ${canMoveLeft ? '' : 'disabled'}>←</button>
                        <button type="button" data-note-move="${escapeHtml(group.id)}" data-note-direction="1" title="Сдвинуть вправо" ${canMoveRight ? '' : 'disabled'}>→</button>
                        <button type="button" data-note-edit="${escapeHtml(group.id)}" title="Переименовать блок">✎</button>
                        <button type="button" data-note-delete="${escapeHtml(group.id)}" title="Удалить блок">×</button>
                    ` : ''}
                    <button type="button" data-note-add="${escapeHtml(group.name)}" title="Добавить задачу в блок">+</button>
                </div>
            </header>
            <div class="note-task-list">
                ${group.events.map((event) => `
                    <article class="note-task ${event.contributes_progress ? 'has-progress' : ''}" data-event-id="${escapeHtml(event.id)}" data-event-source="${escapeHtml(event.source)}" tabindex="0" role="button" aria-label="Открыть задачу ${escapeHtml(event.title)}">
                        <div class="note-task-main">
                            <time>${escapeHtml(formatDateShort(event.date))} · ${escapeHtml(event.time)}</time>
                            <strong>${escapeHtml(event.title)}</strong>
                            ${event.note ? `<small>${escapeHtml(event.note)}</small>` : ''}
                        </div>
                        <div class="note-task-actions">
                            ${!event.is_regular ? `<button class="progress-star ${event.contributes_progress ? 'is-active' : ''}" type="button" data-event-action="progress" title="${event.progress_goal_title ? `Двигает цель: ${escapeHtml(event.progress_goal_title)}` : 'Добавить к прогрессу цели'}">${event.contributes_progress ? '★' : '☆'}</button>` : ''}
                            <button type="button" data-event-action="edit" title="Редактировать">✎</button>
                            <button type="button" data-event-action="delete" title="Удалить">×</button>
                        </div>
                    </article>
                `).join('')}
            </div>
        </article>
    `;
    }).join('');
}

function renderGoalTaskPreview(goal) {
    const tasks = getAllEvents()
        .filter((event) => String(event.progress_goal_id) === String(goal.id) && event.contributes_progress)
        .slice(0, 6);

    if (!tasks.length) {
        return '<p class="goal-empty">Отметьте обычные задачи звездочкой, чтобы они появились здесь.</p>';
    }

    return tasks.map((task) => `
        <div class="goal-task ${task.is_done ? 'is-done' : ''}">
            <span>${task.is_done ? '✓' : '☆'}</span>
            <strong>${escapeHtml(task.title)}</strong>
            <time>${escapeHtml(formatDateShort(task.date))}</time>
        </div>
    `).join('');
}

function renderGoals() {
    const grid = document.querySelector('#goalsGrid');
    if (!grid) return;

    if (!globalGoals.length) {
        grid.innerHTML = '<p class="empty-state">Создайте первую большую цель.</p>';
        return;
    }

    grid.innerHTML = globalGoals.map((goal) => {
        const periodLabel = goal.period === 'other' && goal.target_date
            ? `План до ${formatDateLong(goal.target_date)}`
            : (PERIOD_LABELS[goal.period] || PERIOD_LABELS.other);
        return `
        <article class="goal-card" style="--goal-color: ${escapeHtml(goal.color || '#789dbb')}">
            <div class="goal-orbit" style="--progress: ${escapeHtml(goal.progress || 0)}">
                <span>${escapeHtml(goal.progress || 0)}%</span>
            </div>
            <div class="goal-body">
                <span>${escapeHtml(periodLabel)}</span>
                <h3>${escapeHtml(goal.title)}</h3>
                ${goal.description ? `<p>${escapeHtml(goal.description)}</p>` : ''}
                <div class="goal-stats">${escapeHtml(goal.done_tasks)} из ${escapeHtml(goal.total_tasks)} задач</div>
                <div class="goal-task-preview">${renderGoalTaskPreview(goal)}</div>
            </div>
            <div class="goal-actions">
                <button type="button" data-goal-edit="${escapeHtml(goal.id)}">Редактировать</button>
                <button type="button" data-goal-delete="${escapeHtml(goal.id)}">Удалить</button>
            </div>
        </article>
    `;
    }).join('');
}

function updateDayNavigationButtons() {
    document.querySelectorAll('[data-day-nav]').forEach((button) => {
        const isPrev = button.dataset.dayNav === 'prev';
        button.disabled = isPrev
            ? selectedDayIndex <= 0
            : selectedDayIndex >= plannerDays.length - 1;
    });
}

function updateSelectedCard() {
    document.querySelectorAll('.day-card').forEach((card) => {
        const cardIndex = Number(card.dataset.dayIndex);
        const isSelected = cardIndex === selectedDayIndex;
        const marker = card.querySelector('.selected-marker');

        card.classList.toggle('is-selected', isSelected);
        card.setAttribute('aria-pressed', isSelected ? 'true' : 'false');

        if (marker) {
            marker.hidden = !isSelected;
        }
    });
}

function scrollSelectedCardIntoView() {
    const selectedCard = document.querySelector(`.day-card[data-day-index="${selectedDayIndex}"]`);
    if (!selectedCard) return;

    selectedCard.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
        inline: 'center'
    });
}

function renderCalendarCards() {
    plannerDays.forEach((day) => {
        const card = document.querySelector(`.day-card[data-day-index="${day.index}"]`);
        if (!card) return;

        card.dataset.dayIso = day.iso;
        card.classList.toggle('is-today', Boolean(day.is_today));

        const weekday = card.querySelector('.weekday');
        const dayNumber = card.querySelector('.day-number');
        const month = card.querySelector('.month');
        const randomArt = card.querySelector('.calendar-random-art');

        if (weekday) weekday.textContent = day.weekday;
        if (dayNumber) dayNumber.textContent = day.day;
        if (month) month.textContent = day.month;
        if (randomArt && day.random_art) randomArt.src = day.random_art;

        const eventsList = card.querySelector('.events-list');
        if (eventsList) {
            eventsList.innerHTML = day.events.length
                ? day.events.map(renderCalendarEvent).join('')
                : '<p class="empty-card-state">Нет задач</p>';
        }
    });

    updateSelectedCard();
}

function renderSelectedDay({ shouldScrollCalendar = true } = {}) {
    const day = getSelectedDay();
    if (!day) return;

    const selectedWeekday = document.querySelector('#selectedWeekday');
    const selectedDayNumber = document.querySelector('#selectedDayNumber');
    const selectedMonth = document.querySelector('#selectedMonth');
    const selectedYear = document.querySelector('#selectedYear');
    const selectedDayCaption = document.querySelector('#selectedDayCaption');
    const dailyEventsTitle = document.querySelector('#dailyEventsTitle');
    const dailyEventsList = document.querySelector('#dailyEventsList');
    const dailyRemindersList = document.querySelector('#dailyRemindersList');

    if (selectedWeekday) selectedWeekday.textContent = day.weekday_full;
    if (selectedDayNumber) selectedDayNumber.textContent = day.day;
    if (selectedMonth) selectedMonth.textContent = day.month_full;
    if (selectedYear) selectedYear.textContent = day.year;
    if (selectedDayCaption) selectedDayCaption.textContent = `${day.weekday_full}, ${day.day} ${day.month_full}`;
    if (dailyEventsTitle) dailyEventsTitle.textContent = `Сюжет на ${day.day} ${day.month_full}:`;

    if (dailyEventsList) {
        dailyEventsList.innerHTML = day.events.length
            ? day.events.map(renderEventRow).join('')
            : '<p class="empty-state">На этот день нет задач в календаре.</p>';
        dailyEventsList.scrollTop = 0;
    }

    if (dailyRemindersList) {
        dailyRemindersList.innerHTML = day.reminders?.length
            ? day.reminders.map(renderReminder).join('')
            : '<p>На выбранный день напоминаний нет.</p>';
    }

    updateSelectedCard();
    updateDayNavigationButtons();

    if (shouldScrollCalendar) {
        scrollSelectedCardIntoView();
    }
}

async function refreshCalendar({ keepSelectedIso = null, shouldScrollCalendar = false } = {}) {
    const currentIso = keepSelectedIso || getSelectedDay()?.iso;
    const query = calendarStartIso ? `?start=${encodeURIComponent(calendarStartIso)}` : '';
    const payload = await apiRequest(`/api/calendar${query}`);
    plannerDays = payload.days || [];
    calendarStartIso = payload.start || plannerDays[0]?.iso || calendarStartIso;

    const nextIndex = plannerDays.findIndex((day) => day.iso === currentIso);
    selectedDayIndex = nextIndex >= 0 ? nextIndex : Math.min(selectedDayIndex, plannerDays.length - 1);

    renderCalendarCards();
    renderSelectedDay({ shouldScrollCalendar });
    renderNotesBoard();
    await refreshGoals();
}

function getCalendarWeekScrollOffset(scroller) {
    const firstCard = scroller?.querySelector('.day-card');
    if (!firstCard) return scroller?.clientWidth || 0;
    const scrollerStyles = window.getComputedStyle(scroller);
    const gap = Number.parseFloat(scrollerStyles.columnGap || scrollerStyles.gap || '0') || 0;
    return (firstCard.getBoundingClientRect().width + gap) * 7;
}

function restoreCalendarScrollAfterWeekShift(scroller, weekDelta) {
    if (!scroller) return;
    requestAnimationFrame(() => {
        const maxScroll = scroller.scrollWidth - scroller.clientWidth;
        const weekOffset = getCalendarWeekScrollOffset(scroller);
        if (weekDelta > 0) {
            scroller.scrollLeft = Math.max(0, maxScroll - weekOffset);
        } else {
            scroller.scrollLeft = Math.min(maxScroll, weekOffset);
        }
    });
}

async function shiftCalendarWeeks(weekDelta, { scroller = weekScroller } = {}) {
    if (isShiftingCalendarWeeks) return;
    isShiftingCalendarWeeks = true;
    const baseDate = new Date(`${calendarStartIso || plannerDays[0]?.iso}T12:00:00`);
    baseDate.setDate(baseDate.getDate() + weekDelta * 7);
    calendarStartIso = baseDate.toISOString().slice(0, 10);
    try {
        await refreshCalendar({ keepSelectedIso: getSelectedDay()?.iso, shouldScrollCalendar: false });
        restoreCalendarScrollAfterWeekShift(scroller, weekDelta);
    } finally {
        setTimeout(() => {
            isShiftingCalendarWeeks = false;
        }, 220);
    }
}

function handleCalendarEdgeScroll(scroller) {
    if (isShiftingCalendarWeeks) return;
    const maxScroll = scroller.scrollWidth - scroller.clientWidth;
    if (maxScroll <= 0) return;

    const edgeThreshold = 18;
    if (scroller.scrollLeft <= edgeThreshold) {
        shiftCalendarWeeks(-1, { scroller });
    } else if (scroller.scrollLeft >= maxScroll - edgeThreshold) {
        shiftCalendarWeeks(1, { scroller });
    }
}

function selectDayByIndex(index, { shouldScrollCalendar = false } = {}) {
    if (index < 0 || index >= plannerDays.length) return;
    selectedDayIndex = index;
    renderSelectedDay({ shouldScrollCalendar });
}

function selectToday({ shouldScrollCalendar = true } = {}) {
    const todayIndex = plannerDays.findIndex((day) => day.is_today);
    if (todayIndex >= 0) {
        selectDayByIndex(todayIndex, { shouldScrollCalendar });
    }
}

function findEventById(eventId) {
    for (const day of plannerDays) {
        const event = day.events.find((item) => item.id === eventId);
        if (event) return { event, day };
    }
    return { event: null, day: null };
}

function showFormError(message) {
    if (!formError) return;
    formError.textContent = message;
    formError.hidden = !message;
}

function setRegularFieldsVisibility() {
    const isRegularType = taskType?.value === 'regular';
    const mode = formMode?.value;
    const source = formSource?.value;
    const scope = document.querySelector('input[name="regular_scope"]:checked')?.value || 'occurrence';
    const showRegularFields = isRegularType && (mode === 'create' || source !== 'regular' || scope === 'series');
    const isSingleRegularOccurrence = mode === 'edit' && source === 'regular' && scope === 'occurrence';

    if (taskDate) {
        taskDate.disabled = isSingleRegularOccurrence;
        taskDate.title = isSingleRegularOccurrence ? 'Для одного регулярного занятия пока меняем время, название и заметку без переноса даты.' : '';
    }

    if (regularFields) regularFields.hidden = !showRegularFields;
    if (regularCounterStartLabel) {
        regularCounterStartLabel.textContent = mode === 'edit' && source === 'regular'
            ? 'Номер выбранного занятия'
            : 'Начало отсчёта';
    }
    if (formHint) {
        formHint.textContent = showRegularFields
            ? 'Для регулярных задач счётчик считается автоматически от даты начала серии.'
            : 'Будет изменён только выбранный экземпляр регулярной задачи.';
    }
}

function resetForm() {
    taskForm.reset();
    showFormError('');
    formMode.value = 'create';
    formSource.value = 'task';
    formDatabaseId.value = '';
    formOriginalDate.value = '';
    taskType.disabled = false;
    taskDate.disabled = false;
    taskDate.title = '';
    taskReminderDays.value = '';
    taskGroupName.value = '';
    setColorValue(taskGroupColor, '#789dbb');
    taskPriority.value = 'normal';
    if (taskProgressGoal) taskProgressGoal.value = '';
    if (taskContributesProgress) taskContributesProgress.checked = false;
    regularScopeBlock.hidden = true;
    document.querySelector('input[name="regular_scope"][value="occurrence"]').checked = true;
    regularCounterLabel.value = 'урок';
    regularCounterStart.value = '1';
    if (regularCounterStartLabel) regularCounterStartLabel.textContent = 'Начало отсчёта';
}

function openModal() {
    if (!modal) return;
    modal.hidden = false;
    document.body.classList.add('modal-open');
    setTimeout(() => taskTitle?.focus(), 0);
}

function closeModal() {
    if (!modal) return;
    modal.hidden = true;
    document.body.classList.remove('modal-open');
    showFormError('');
}

function showGroupFormError(message) {
    if (!groupFormError) return;
    groupFormError.textContent = message;
    groupFormError.hidden = !message;
}

function openGroupModal(group = null) {
    if (!groupModal || !groupForm) return;
    groupForm.reset();
    showGroupFormError('');
    groupFormId.value = group?.id || '';
    groupModalTitle.textContent = group ? 'Редактировать блок' : 'Новый блок';
    groupName.value = group?.name || '';
    setColorValue(groupColor, group?.color || '#789dbb');
    groupModal.hidden = false;
    document.body.classList.add('modal-open');
    setTimeout(() => groupName?.focus(), 0);
}

function closeGroupModal() {
    if (!groupModal) return;
    groupModal.hidden = true;
    document.body.classList.remove('modal-open');
    showGroupFormError('');
}

function openCreateModal(isoDate) {
    resetForm();
    const weekday = getDateWeekdayNumber(isoDate);

    modalTitle.textContent = 'Новая задача';
    taskDate.value = isoDate;
    taskType.value = 'task';
    taskStartTime.value = '10:00';
    taskEndTime.value = '11:00';
    setSelectedRegularWeekdays([weekday]);
    regularStartDate.value = isoDate;
    regularCounterLabel.value = 'урок';
    regularCounterStart.value = '1';
    setRegularFieldsVisibility();
    openModal();
}

function openEditModal(event) {
    resetForm();

    modalTitle.textContent = event.is_regular ? 'Редактировать регулярную задачу' : 'Редактировать задачу';
    formMode.value = 'edit';
    formSource.value = event.source;
    formDatabaseId.value = String(event.database_id);
    formOriginalDate.value = event.date;

    taskTitle.value = event.title || '';
    taskDate.value = event.date || getSelectedDay().iso;
    taskStartTime.value = event.start_time || '10:00';
    taskEndTime.value = event.end_time || '11:00';
    taskNote.value = event.note || '';
    taskReminderDays.value = (event.reminder_days || []).join(', ');
    taskGroupName.value = event.group_name || '';
    setColorValue(taskGroupColor, event.group_color || '#789dbb');
    taskPriority.value = event.priority || 'normal';
    if (taskProgressGoal) taskProgressGoal.value = event.progress_goal_id || '';
    if (taskContributesProgress) taskContributesProgress.checked = Boolean(event.contributes_progress);
    taskType.value = event.is_regular ? 'regular' : 'task';
    taskType.disabled = true;

    if (event.is_regular) {
        regularScopeBlock.hidden = false;
        setSelectedRegularWeekdays(event.weekdays || [event.weekday ?? getDateWeekdayNumber(event.date)]);
        regularStartDate.value = event.series_start_date || event.date;
        regularCounterLabel.value = event.counter_label || 'урок';
        regularCounterStart.value = String(event.occurrence_number || event.counter_start || 1);
    }

    setRegularFieldsVisibility();
    openModal();
}

function collectTaskPayload() {
    return {
        title: taskTitle.value.trim(),
        date: taskDate.value,
        start_time: taskStartTime.value,
        end_time: taskEndTime.value,
        note: taskNote.value.trim(),
        reminder_days: taskReminderDays.value,
        group_name: taskGroupName.value.trim(),
        group_color: taskGroupColor.value,
        priority: taskPriority.value,
        progress_goal_id: taskProgressGoal?.value || null,
        contributes_progress: Boolean(taskContributesProgress?.checked)
    };
}

function collectRegularPayload() {
    let counterStart = Number(regularCounterStart.value || 1);

    if (formMode.value === 'edit' && formSource.value === 'regular') {
        const offset = getOccurrenceOffset(
            regularStartDate.value || taskDate.value,
            getSelectedRegularWeekdays(),
            formOriginalDate.value || taskDate.value
        );
        counterStart -= offset;
    }

    return {
        ...collectTaskPayload(),
        weekday: getSelectedRegularWeekdays()[0],
        weekdays: getSelectedRegularWeekdays(),
        start_date: regularStartDate.value || taskDate.value,
        counter_label: regularCounterLabel.value.trim() || 'раз',
        counter_start: counterStart
    };
}

async function handleFormSubmit(event) {
    event.preventDefault();
    showFormError('');

    const mode = formMode.value;
    const source = formSource.value;
    const databaseId = formDatabaseId.value;
    const originalDate = formOriginalDate.value;
    const selectedIsoAfterSave = taskDate.value || getSelectedDay().iso;

    try {
        if (mode === 'create') {
            if (taskType.value === 'regular') {
                await apiRequest('/api/regular-tasks', {
                    method: 'POST',
                    body: JSON.stringify(collectRegularPayload())
                });
            } else {
                await apiRequest('/api/tasks', {
                    method: 'POST',
                    body: JSON.stringify(collectTaskPayload())
                });
            }
        } else if (source === 'regular') {
            const scope = document.querySelector('input[name="regular_scope"]:checked')?.value || 'occurrence';
            if (scope === 'series') {
                await apiRequest(`/api/regular-tasks/${databaseId}`, {
                    method: 'PATCH',
                    body: JSON.stringify(collectRegularPayload())
                });
            } else {
                await apiRequest(`/api/regular-occurrences/${databaseId}/${originalDate}`, {
                    method: 'PATCH',
                    body: JSON.stringify(collectTaskPayload())
                });
            }
        } else {
            await apiRequest(`/api/tasks/${databaseId}`, {
                method: 'PATCH',
                body: JSON.stringify(collectTaskPayload())
            });
        }

        closeModal();
        await refreshCalendar({ keepSelectedIso: selectedIsoAfterSave, shouldScrollCalendar: true });
    } catch (error) {
        showFormError(error.message);
    }
}

async function deleteEvent(event) {
    const isRegular = event.is_regular;
    let deleteSeries = false;

    if (isRegular) {
        const shouldDelete = window.confirm(`Удалить регулярную задачу «${event.title}»?`);
        if (!shouldDelete) return;

        deleteSeries = window.confirm(
            'Удалить всю серию?\n\nОК — удалить всю серию.\nОтмена — удалить только это занятие.'
        );
    } else if (!window.confirm(`Удалить задачу «${event.title}»?`)) {
        return;
    }

    try {
        if (isRegular && deleteSeries) {
            await apiRequest(`/api/regular-tasks/${event.database_id}`, { method: 'DELETE' });
        } else if (isRegular) {
            await apiRequest(`/api/regular-occurrences/${event.database_id}/${event.date}`, { method: 'DELETE' });
        } else {
            await apiRequest(`/api/tasks/${event.database_id}`, { method: 'DELETE' });
        }

        await refreshCalendar({ keepSelectedIso: getSelectedDay().iso });
    } catch (error) {
        alert(error.message);
    }
}

async function toggleTaskDone(event, checkbox) {
    if (event.is_regular) return;

    try {
        await apiRequest(`/api/tasks/${event.database_id}/done`, {
            method: 'PATCH',
            body: JSON.stringify({ is_done: checkbox.checked })
        });
        await refreshCalendar({ keepSelectedIso: getSelectedDay().iso });
    } catch (error) {
        checkbox.checked = !checkbox.checked;
        alert(error.message);
    }
}

async function toggleTaskProgress(event) {
    if (event.is_regular) return;

    if (!globalGoals.length) {
        switchView('inspiration');
        goalTitle?.focus();
        return;
    }

    const choices = globalGoals
        .map((goal, index) => `${index + 1}. ${goal.title}`)
        .join('\n');
    const currentIndex = globalGoals.findIndex((goal) => String(goal.id) === String(event.progress_goal_id));
    const promptText = event.contributes_progress
        ? `Выберите раздел вдохновения для задачи или введите 0, чтобы убрать звездочку:\n\n${choices}`
        : `Выберите раздел вдохновения для задачи:\n\n${choices}`;
    const answer = window.prompt(promptText, String(Math.max(currentIndex + 1, 1)));
    if (answer === null) return;

    const selectedNumber = Number(answer.trim());
    if (event.contributes_progress && selectedNumber === 0) {
        await saveTaskProgress(event, event.progress_goal_id, false);
        return;
    }

    const selectedGoal = globalGoals[selectedNumber - 1];
    if (!selectedGoal) {
        alert('Выберите номер из списка целей.');
        return;
    }

    await saveTaskProgress(event, selectedGoal.id, true);
}

async function saveTaskProgress(event, goalId, contributesProgress) {
    try {
        await apiRequest(`/api/tasks/${event.database_id}`, {
            method: 'PATCH',
            body: JSON.stringify({
                title: event.title,
                date: event.date,
                start_time: event.start_time,
                end_time: event.end_time,
                note: event.note || '',
                reminder_days: event.reminder_days || [],
                group_name: event.group_name || '',
                group_color: event.group_color || '#789dbb',
                priority: event.priority || 'normal',
                progress_goal_id: goalId,
                contributes_progress: contributesProgress
            })
        });
        await refreshCalendar({ keepSelectedIso: getSelectedDay().iso });
    } catch (error) {
        alert(error.message);
    }
}

function handleEventActionClick(button) {
    const container = button.closest('[data-event-id]');
    if (!container) return;

    const { event } = findEventById(container.dataset.eventId);
    if (!event) return;

    if (button.dataset.eventAction === 'edit') {
        openEditModal(event);
    }

    if (button.dataset.eventAction === 'progress') {
        toggleTaskProgress(event);
    }

    if (button.dataset.eventAction === 'delete') {
        deleteEvent(event);
    }
}

weekScroller?.addEventListener('click', (event) => {
    const actionButton = event.target.closest('[data-event-action]');
    if (actionButton) {
        event.stopPropagation();
        handleEventActionClick(actionButton);
        return;
    }

    const addButton = event.target.closest('[data-add-day]');
    if (addButton) {
        event.stopPropagation();
        const card = addButton.closest('.day-card');
        if (!card) return;
        const index = Number(card.dataset.dayIndex);
        selectDayByIndex(index, { shouldScrollCalendar: false });
        openCreateModal(card.dataset.dayIso);
        return;
    }

    const card = event.target.closest('.day-card[data-day-index]');
    if (card) {
        selectDayByIndex(Number(card.dataset.dayIndex), { shouldScrollCalendar: false });
    }
});

weekScroller?.addEventListener('keydown', (event) => {
    const card = event.target.closest('.day-card[data-day-index]');
    if (!card || (event.key !== 'Enter' && event.key !== ' ')) return;

    event.preventDefault();
    selectDayByIndex(Number(card.dataset.dayIndex), { shouldScrollCalendar: false });
});

document.querySelector('#dailyEventsList')?.addEventListener('click', (event) => {
    const actionButton = event.target.closest('[data-event-action]');
    if (actionButton) {
        event.preventDefault();
        handleEventActionClick(actionButton);
        return;
    }
});

document.querySelector('#dailyEventsList')?.addEventListener('change', (event) => {
    const checkbox = event.target.closest('input[type="checkbox"]');
    if (!checkbox) return;

    const row = checkbox.closest('[data-event-id]');
    const { event: plannerEvent } = findEventById(row?.dataset.eventId);
    if (!plannerEvent) return;

    toggleTaskDone(plannerEvent, checkbox);
});

document.querySelectorAll('[data-day-nav]').forEach((button) => {
    button.addEventListener('click', () => {
        const direction = button.dataset.dayNav === 'next' ? 1 : -1;
        selectDayByIndex(selectedDayIndex + direction, { shouldScrollCalendar: true });
    });
});

document.querySelector('[data-go-today]')?.addEventListener('click', () => {
    selectToday({ shouldScrollCalendar: true });
});

document.querySelectorAll('[data-open-create-selected]').forEach((button) => {
    button.addEventListener('click', () => openCreateModal(getSelectedDay().iso));
});

document.querySelectorAll('[data-view-link]').forEach((button) => {
    button.addEventListener('click', () => switchView(button.dataset.viewLink));
});

document.querySelectorAll('[data-open-view]').forEach((button) => {
    button.addEventListener('click', () => switchView(button.dataset.openView));
});

document.querySelector('#notesBoard')?.addEventListener('click', (event) => {
    const taskActionButton = event.target.closest('[data-event-action]');
    if (taskActionButton) {
        event.preventDefault();
        handleEventActionClick(taskActionButton);
        return;
    }

    const moveButton = event.target.closest('[data-note-move]');
    if (moveButton) {
        const groupId = String(moveButton.dataset.noteMove);
        const direction = Number(moveButton.dataset.noteDirection);
        const currentIndex = taskGroups.findIndex((group) => String(group.id) === groupId);
        const nextIndex = currentIndex + direction;
        if (currentIndex < 0 || nextIndex < 0 || nextIndex >= taskGroups.length) return;

        const reorderedGroups = [...taskGroups];
        [reorderedGroups[currentIndex], reorderedGroups[nextIndex]] = [reorderedGroups[nextIndex], reorderedGroups[currentIndex]];

        apiRequest('/api/task-groups/reorder', {
            method: 'PATCH',
            body: JSON.stringify({ ids: reorderedGroups.map((group) => group.id) })
        })
            .then(() => refreshTaskGroups())
            .catch((error) => alert(error.message));
        return;
    }

    const editButton = event.target.closest('[data-note-edit]');
    if (editButton) {
        const group = taskGroups.find((item) => String(item.id) === String(editButton.dataset.noteEdit));
        if (!group) return;
        openGroupModal(group);
        return;
    }

    const deleteButton = event.target.closest('[data-note-delete]');
    if (deleteButton) {
        const group = taskGroups.find((item) => String(item.id) === String(deleteButton.dataset.noteDelete));
        if (!group) return;
        if (!window.confirm(`Удалить группу «${group.name}»?\n\nЗадачи останутся, но перейдут в «Без группы».`)) return;

        apiRequest(`/api/task-groups/${group.id}`, { method: 'DELETE' })
            .then(() => refreshTaskGroups())
            .then(() => refreshCalendar({ keepSelectedIso: getSelectedDay().iso }))
            .catch((error) => alert(error.message));
        return;
    }

    const addButton = event.target.closest('[data-note-add]');
    if (addButton) {
        openCreateModal(getSelectedDay().iso);
        taskGroupName.value = addButton.dataset.noteAdd === 'Без группы' ? '' : addButton.dataset.noteAdd;
        setColorValue(taskGroupColor, document.querySelector(`#taskGroupsList option[value="${CSS.escape(taskGroupName.value)}"]`)?.dataset.color || '#789dbb');
        return;
    }

    const taskCard = event.target.closest('.note-task[data-event-id]');
    if (!taskCard) return;
    const { event: plannerEvent } = findEventById(taskCard.dataset.eventId);
    if (plannerEvent) openEditModal(plannerEvent);
});

document.querySelector('#notesBoard')?.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    const taskCard = event.target.closest('.note-task[data-event-id]');
    if (!taskCard || event.target.closest('button')) return;

    event.preventDefault();
    const { event: plannerEvent } = findEventById(taskCard.dataset.eventId);
    if (plannerEvent) openEditModal(plannerEvent);
});

document.querySelector('[data-create-note-block]')?.addEventListener('click', async () => {
    openGroupModal();
});

monthProgressSelect?.addEventListener('change', updateMonthProgress);
goalPeriod?.addEventListener('change', updateGoalTargetDateVisibility);

goalForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const payload = {
        title: goalTitle.value.trim(),
        period: goalPeriod.value,
        target_date: goalPeriod.value === 'other' ? goalTargetDate?.value || null : null,
        description: goalDescription.value.trim(),
        color: goalColor.value
    };

    try {
        const goalId = goalFormId.value;
        await apiRequest(goalId ? `/api/global-goals/${goalId}` : '/api/global-goals', {
            method: goalId ? 'PATCH' : 'POST',
            body: JSON.stringify(payload)
        });
        goalForm.reset();
        goalFormId.value = '';
        updateGoalTargetDateVisibility();
        await refreshGoals();
    } catch (error) {
        alert(error.message);
    }
});

document.querySelector('#goalFormReset')?.addEventListener('click', () => {
    goalForm?.reset();
    if (goalFormId) goalFormId.value = '';
    setColorValue(goalColor, '#789dbb');
    updateGoalTargetDateVisibility();
});

groupForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    showGroupFormError('');

    const payload = {
        name: groupName.value.trim(),
        color: groupColor.value
    };
    const groupId = groupFormId.value;

    try {
        await apiRequest(groupId ? `/api/task-groups/${groupId}` : '/api/task-groups', {
            method: groupId ? 'PATCH' : 'POST',
            body: JSON.stringify(payload)
        });
        closeGroupModal();
        await refreshTaskGroups();
        await refreshCalendar({ keepSelectedIso: getSelectedDay().iso });
    } catch (error) {
        showGroupFormError(error.message);
    }
});

document.querySelectorAll('[data-close-group-modal]').forEach((button) => {
    button.addEventListener('click', closeGroupModal);
});

groupModal?.addEventListener('click', (event) => {
    if (event.target === groupModal) closeGroupModal();
});

document.querySelector('#goalsGrid')?.addEventListener('click', async (event) => {
    const editButton = event.target.closest('[data-goal-edit]');
    if (editButton) {
        const goal = findGoal(editButton.dataset.goalEdit);
        if (!goal) return;
        goalFormId.value = goal.id;
        goalTitle.value = goal.title;
        goalPeriod.value = goal.period;
        if (goalTargetDate) goalTargetDate.value = goal.target_date || '';
        goalDescription.value = goal.description || '';
        setColorValue(goalColor, goal.color || '#789dbb');
        updateGoalTargetDateVisibility();
        goalTitle.focus();
        return;
    }

    const deleteButton = event.target.closest('[data-goal-delete]');
    if (!deleteButton) return;
    const goal = findGoal(deleteButton.dataset.goalDelete);
    if (!goal || !window.confirm(`Удалить цель «${goal.title}»?`)) return;

    try {
        await apiRequest(`/api/global-goals/${goal.id}`, { method: 'DELETE' });
        await refreshCalendar({ keepSelectedIso: getSelectedDay().iso });
    } catch (error) {
        alert(error.message);
    }
});

taskGroupName?.addEventListener('change', () => {
    const option = document.querySelector(`#taskGroupsList option[value="${CSS.escape(taskGroupName.value)}"]`);
    const color = option?.dataset.color;
    if (color && taskGroupColor) setColorValue(taskGroupColor, color);
});

document.querySelector('[data-import-schedule]')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = 'Импорт...';

    try {
        const payload = await apiRequest('/api/university-schedule/import', {
            method: 'POST',
            body: JSON.stringify({
                url: button.dataset.scheduleUrl,
                start_date: getSelectedDay().iso,
                weeks: 5
            })
        });
        await refreshCalendar({ keepSelectedIso: getSelectedDay().iso, shouldScrollCalendar: false });
        alert(payload.message || 'Расписание импортировано.');
    } catch (error) {
        alert(error.message);
    } finally {
        button.disabled = false;
        button.textContent = originalText;
    }
});

document.querySelectorAll('[data-close-modal]').forEach((button) => {
    button.addEventListener('click', closeModal);
});

modal?.addEventListener('click', (event) => {
    if (event.target === modal) closeModal();
});

document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal && !modal.hidden) {
        closeModal();
    }
    if (event.key === 'Escape' && groupModal && !groupModal.hidden) {
        closeGroupModal();
    }
});

taskType?.addEventListener('change', () => {
    if (taskType.value === 'regular') {
        setSelectedRegularWeekdays([getDateWeekdayNumber(taskDate.value || getSelectedDay().iso)]);
        regularStartDate.value = taskDate.value || getSelectedDay().iso;
    }
    setRegularFieldsVisibility();
});

taskDate?.addEventListener('change', () => {
    if (taskType.value === 'regular' && formMode.value === 'create') {
        setSelectedRegularWeekdays([getDateWeekdayNumber(taskDate.value)]);
        regularStartDate.value = taskDate.value;
    }
});

document.querySelectorAll('input[name="regular_scope"]').forEach((radio) => {
    radio.addEventListener('change', setRegularFieldsVisibility);
});

taskForm?.addEventListener('submit', handleFormSubmit);

renderColorPalettes();
readTaskGroupsFromDatalist();
setColorValue(taskGroupColor, taskGroupColor?.value || '#789dbb');
setColorValue(goalColor, goalColor?.value || '#789dbb');
setColorValue(groupColor, groupColor?.value || '#789dbb');
updateGoalTargetDateVisibility();
updateGoalOptions();
renderCalendarCards();
renderSelectedDay({ shouldScrollCalendar: false });
renderNotesBoard();
renderGoals();
