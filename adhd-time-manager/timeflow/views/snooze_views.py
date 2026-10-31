"""Snooze: מקום לעצור, לפרוק מחשבות, לקבל הצעה לצעד קטן ולחזור לפעולה.

ההצעות נוצרות בשרת בלבד (snooze_assistant). הדפדפן מקבל רק את הטקסט המוכן.
כשלוחצים על הצעה, השרת קורא אותה מהמסד לפי מספר, ולא סומך על טקסט שנשלח מהטופס.
"""
from flask import abort, g, redirect, request, url_for

from .. import clock, focus_timer, planner, snooze_assistant
from ..ai_providers import Suggestion
from . import back, bp, page, repo, say, uid

BUCKETS = ("unsorted", "action", "later", "let_go")


def owned_entry(entry_id):
    entry = repo().get_snooze_entry(uid(), entry_id)
    if not entry:
        abort(404)
    return entry


def with_suggestion(entry):
    entry = dict(entry)
    entry["suggestion"] = Suggestion.from_json(entry["ai_reply"]) if entry["ai_reply"] else None
    return entry


def entry_option(entry, index):
    suggestion = Suggestion.from_json(entry["ai_reply"]) if entry["ai_reply"] else None
    if not suggestion or not 0 <= index < len(suggestion.options):
        abort(404)
    return suggestion.options[index]


@bp.route("/snooze")
def snooze():
    r, user_id, now = repo(), uid(), clock.now()
    entries = [with_suggestion(e) for e in r.list_snooze_entries(user_id)]
    current = request.args.get("entry", type=int)
    focus_entry = next((e for e in entries if e["id"] == current), None)
    help_task = None
    help_id = request.args.get("help", type=int)
    if help_id:
        help_task = r.get_task(user_id, help_id)
    active = r.active_session(user_id)
    timed = planner.next_timed_task(r.list_tasks(user_id), now)
    return page("zehava/snooze.html", active="snooze",
                entries=[e for e in entries if e is not focus_entry], focus_entry=focus_entry,
                help_task=help_task, buckets=BUCKETS, timed_task=timed,
                back_task_id=active["task_id"] if active else None,
                snooze_options=planner.SNOOZE_OPTIONS,
                ai_ready=bool(g.settings["ai_enabled"]) and snooze_assistant.provider().name != "offline")


@bp.route("/snooze/write", methods=["POST"])
def snooze_write():
    body = (request.form.get("text") or "").strip()[:1000]
    if not body:
        return redirect(url_for("zehava.snooze") + "#write")
    entry_id = repo().create_snooze_entry(uid(), body)
    return redirect(url_for("zehava.snooze", entry=entry_id) + "#current")


@bp.route("/snooze/<int:entry_id>/suggest", methods=["POST"])
def snooze_suggest(entry_id):
    entry = owned_entry(entry_id)
    suggestion = snooze_assistant.suggest(repo(), uid(), g.settings, "unload", entry["body"])
    repo().update_snooze_entry(uid(), entry_id, ai_reply=suggestion.to_json())
    return redirect(url_for("zehava.snooze", entry=entry_id) + "#current")


@bp.route("/snooze/help/<int:task_id>", methods=["GET", "POST"])
def snooze_help(task_id):
    # "קשה להתחיל?": הצעה לצעד ראשון קטן מאוד למשימה מסוימת
    task = repo().get_task(uid(), task_id)
    if not task:
        abort(404)
    if request.method == "GET":
        return redirect(url_for("zehava.snooze", help=task_id) + "#help")
    suggestion = snooze_assistant.suggest(repo(), uid(), g.settings, "start_help", task["title"],
                                          {"prefer_short": True})
    entry_id = repo().create_snooze_entry(uid(), task["title"])
    repo().update_snooze_entry(uid(), entry_id, bucket="action", task_id=task_id, ai_reply=suggestion.to_json())
    return redirect(url_for("zehava.snooze", entry=entry_id) + "#current")


@bp.route("/snooze/<int:entry_id>/option/<int:index>/<action>", methods=["POST"])
def snooze_option(entry_id, index, action):
    # מה עושים עם הצעה: להוסיף למשימות, להתחיל טיימר, או להוסיף כצעד למשימה המקורית
    entry = owned_entry(entry_id)
    option = entry_option(entry, index)
    source = "ai" if Suggestion.from_json(entry["ai_reply"]).source == "claude" else "snooze"
    if action == "step" and entry["task_id"]:
        repo().add_step(uid(), entry["task_id"], option.title[:120])
        say("note_moved_step")
        return redirect(url_for("zehava.tasks", open=entry["task_id"]) + f"#task-{entry['task_id']}")
    if action not in ("task", "timer"):
        abort(404)
    task_id = repo().create_task(uid(), option.title, source=source)
    if not entry["task_id"]:
        repo().update_snooze_entry(uid(), entry_id, bucket="action", task_id=task_id)
    if action == "timer":
        if focus_timer.start(repo(), uid(), "focus", option.minutes, task_id) is None:
            say("already_running", "warn")
        return redirect(url_for("zehava.focus", task=task_id))
    say("moved_to_task")
    return redirect(url_for("zehava.tasks") + f"#task-{task_id}")


@bp.route("/snooze/<int:entry_id>/sort/<bucket>", methods=["POST"])
def snooze_sort(entry_id, bucket):
    if bucket not in BUCKETS:
        abort(404)
    owned_entry(entry_id)
    repo().update_snooze_entry(uid(), entry_id, bucket=bucket)
    return back("zehava.snooze")


@bp.route("/snooze/<int:entry_id>/to-task", methods=["POST"])
def snooze_to_task(entry_id):
    entry = owned_entry(entry_id)
    task_id = repo().create_task(uid(), " ".join(entry["body"].split())[:200], source="snooze")
    repo().update_snooze_entry(uid(), entry_id, bucket="action", task_id=task_id)
    say("moved_to_task")
    return back("zehava.snooze")


@bp.route("/snooze/<int:entry_id>/delete", methods=["POST"])
def snooze_delete(entry_id):
    repo().delete_snooze_entry(uid(), entry_id)
    return back("zehava.snooze")


@bp.route("/snooze/<int:minutes>", methods=["POST"])
def postpone(minutes):
    # מגרסה 1: דחיית המשימה הבאה עם שעה. התאריך מתעדכן נכון גם אחרי חצות
    if minutes not in planner.SNOOZE_OPTIONS:
        abort(404)
    now = clock.now()
    task = planner.next_timed_task(repo().list_tasks(uid()), now)
    if task:
        day, at = planner.postpone(task, minutes, now)
        repo().snooze_task(uid(), task["id"], day, at)
        say("postponed", time=at if day == now.date().isoformat() else f"{at} ({day})")
    return back("zehava.snooze")
