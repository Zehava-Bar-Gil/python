"""רשימת המטלות: משימות, צעדים קטנים, עדיפות ותאריך."""
from flask import abort, g, redirect, request, url_for

from .. import clock, journey, planner, ui
from ..texts import TAGS
from . import back, bp, form_date, form_text, mark_just, page, repo, say, tr, uid

FIRST_SHOWN = 7     # תצוגה הדרגתית: רק המשימות הראשונות, והשאר בלחיצה


def task_fields():
    # קורא ומנקה את שדות המשימה מהטופס. ערך לא תקין פשוט לא נשמר
    # התאריך מגיע משלוש רשימות (יום, חודש, שנה), כמו יום ההולדת
    day, filled = form_date("due")
    if filled and not day:
        say("date_invalid", "warn")
    due_date, due_time = planner.clean_due(day.isoformat() if day else None, request.form.get("due_time"))
    tag = request.form.get("tag", "")
    priority = request.form.get("priority", "normal")
    return {
        "title": form_text("title", 200),
        "details": (request.form.get("details") or "").strip()[:1000],
        "tag": tag if tag in TAGS else "",
        "priority": priority if priority in planner.PRIORITIES else "normal",
        "due_date": due_date,
        "due_time": due_time,
        "estimate_minutes": planner.clean_estimate(request.form.get("estimate")),
    }


def owned_task(task_id):
    task = repo().get_task(uid(), task_id)
    if not task:
        abort(404)
    return task


@bp.route("/tasks")
def tasks():
    r, user_id = repo(), uid()
    tag = request.args.get("tag") if request.args.get("tag") in TAGS else None
    show_done = request.args.get("show") == "done"
    show_all = request.args.get("all") == "1"
    everything = r.list_tasks(user_id, tag=tag)
    if show_done:
        listed = sorted((t for t in everything if t["status"] == "done"), key=lambda t: t["completed_at"] or "",
                        reverse=True)
    else:
        listed = planner.open_tasks(everything)
    hidden = 0 if show_all else max(0, len(listed) - FIRST_SHOWN)
    listed = listed if show_all else listed[:FIRST_SHOWN]
    planner.attach_steps(listed, r.steps_for_tasks(user_id, [t["id"] for t in listed]))
    today = clock.today()
    for task in listed:
        task["waiting_since"] = planner.waiting_since(task, today)
        task["split_hint"] = planner.needs_split_hint(task)
    total = planner.estimate_total(everything)
    estimate_total = ui.minutes_label(tr(), total * 60) if total else None
    return page("zehava/tasks.html", active="todo", tasks=listed, hidden=hidden, tag_filter=tag,
                show_done=show_done, open_count=sum(1 for t in everything if t["status"] == "open"),
                done_count=sum(1 for t in everything if t["status"] == "done"),
                open_task=request.args.get("open", type=int), priorities=planner.PRIORITIES, due_years=ui.due_years(),
                estimates=planner.ESTIMATES, estimate_total=estimate_total)


@bp.route("/add", methods=["POST"])
def add():
    fields = task_fields()
    if not fields["title"]:
        say("title_required", "warn")
    else:
        repo().create_task(uid(), **fields)
        say("task_added")
    return back("zehava.tasks")


@bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id):
    task = owned_task(task_id)
    if request.method == "POST":
        fields = task_fields()
        if fields["title"]:
            repo().update_task(uid(), task_id, **fields)
            say("task_saved")
            return redirect(url_for("zehava.tasks") + f"#task-{task_id}")
        say("title_required", "warn")
    return page("zehava/task_edit.html", active="todo", task=task, priorities=planner.PRIORITIES,
                estimates=planner.ESTIMATES, due_years=ui.due_years(task["due_date"]))


@bp.route("/toggle/<int:task_id>", methods=["POST"])
def toggle(task_id):
    # סימון כבוצע נותן 3 נקודות במסע. ביטול הסימון מבטל אותן (תיקון, לא עונש)
    task = owned_task(task_id)
    if task["status"] == "open":
        if repo().set_task_done(uid(), task_id, True):
            journey.record(repo(), uid(), "task", task_id)
            say("task_done_undo", title=task["title"], task_id=task_id)   # עם כפתור "ביטול", למקרה של לחיצה בטעות
    elif repo().set_task_done(uid(), task_id, False):
        journey.unrecord(repo(), uid(), "task", task_id)
    mark_just("task", task_id)
    return back("zehava.tasks")


@bp.route("/delete/<int:task_id>", methods=["POST"])
def delete(task_id):
    # הנקודות שכבר נצברו נשארות: העבודה נעשתה גם אם המשימה נמחקה
    if repo().delete_task(uid(), task_id):
        say("task_deleted")
    return back("zehava.tasks")


@bp.route("/steps/add/<int:task_id>", methods=["POST"])
def step_add(task_id):
    title = form_text("text", 120)
    if title:
        step_id = repo().add_step(uid(), task_id, title)
        if step_id:
            mark_just("step", step_id, task_id)
    return back("zehava.tasks", open=task_id)


@bp.route("/steps/toggle/<int:task_id>/<int:step_id>", methods=["POST"])
def step_toggle(task_id, step_id):
    step = repo().get_step(uid(), task_id, step_id)
    if not step:
        abort(404)
    done = not step["done_at"]
    repo().set_step_done(uid(), task_id, step_id, done)
    if done:
        journey.record(repo(), uid(), "step", step_id)
        repo().mark_task_started(uid(), task_id)
    else:
        journey.unrecord(repo(), uid(), "step", step_id)
    mark_just("step", step_id, task_id)
    return back("zehava.tasks", open=task_id)


@bp.route("/steps/delete/<int:task_id>/<int:step_id>", methods=["POST"])
def step_delete(task_id, step_id):
    repo().delete_step(uid(), task_id, step_id)
    return back("zehava.tasks", open=task_id)


def task_options():
    # לרשימות בחירה (פתק לצעד, טיימר): המשימות הפתוחות לפי הסדר
    return planner.open_tasks(repo().list_tasks(g.user["id"]))
