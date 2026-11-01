"""פתקיות: כתיבה מהירה בכתב יד, תגית, והעברה למשימה, לצעד או ל-Snooze."""
from flask import abort, redirect, request, url_for

from . import back, bp, form_text, mark_just, page, repo, say, uid
from .task_views import task_options

COLORS = ["yellow", "pink", "green", "blue"]


def note_fields():
    color = request.form.get("color")
    return {
        "body": (request.form.get("text") or "").strip()[:500],
        "color": color if color in COLORS else "yellow",
        "tag": form_text("tag", 30),
    }


def owned_note(note_id):
    note = repo().get_note(uid(), note_id)
    if not note:
        abort(404)
    return note


@bp.route("/notes")
def notes():
    tag = request.args.get("tag") or None
    return page("zehava/notes.html", active="notes", notes=repo().list_notes(uid(), tag=tag),
                note_tags=repo().note_tags(uid()), tag_filter=tag, colors=COLORS, task_choices=task_options())


@bp.route("/notes/add", methods=["POST"])
def note_add():
    fields = note_fields()
    if fields["body"]:
        note_id = repo().create_note(uid(), **fields)
        say("note_added")
        mark_just("note", note_id)
    return back("zehava.notes")


@bp.route("/notes/<int:note_id>/edit", methods=["GET", "POST"])
def note_edit(note_id):
    note = owned_note(note_id)
    if request.method == "POST":
        fields = note_fields()
        if fields["body"]:
            repo().update_note(uid(), note_id, **fields)
            say("note_saved")
            mark_just("note", note_id)
            return redirect(url_for("zehava.notes") + f"#note-{note_id}")
    return page("zehava/note_edit.html", active="notes", note=note, colors=COLORS)


@bp.route("/notes/<int:note_id>/pin", methods=["POST"])
def note_pin(note_id):
    # הצמדה: פתק חשוב עולה לראש הלוח, וגם לדף הבית. לחיצה נוספת מורידה אותו בחזרה
    note = owned_note(note_id)
    repo().set_note_pinned(uid(), note_id, not note["pinned"])
    say("note_unpinned" if note["pinned"] else "note_pinned")
    mark_just("note", note_id)
    return back("zehava.notes")


@bp.route("/notes/delete/<int:note_id>", methods=["POST"])
def note_delete(note_id):
    if repo().delete_note(uid(), note_id):
        say("note_deleted")
    return back("zehava.notes")


# ---------- העברת פתק: הפתק הופך לפריט החדש ונמחק מהפתקיות ----------
@bp.route("/notes/<int:note_id>/to-task", methods=["POST"])
def note_to_task(note_id):
    note = owned_note(note_id)
    task_id = repo().create_task(uid(), " ".join(note["body"].split())[:200], source="note")
    repo().delete_note(uid(), note_id)
    say("note_moved_task")
    return redirect(url_for("zehava.tasks") + f"#task-{task_id}")


@bp.route("/notes/<int:note_id>/to-step", methods=["POST"])
def note_to_step(note_id):
    note = owned_note(note_id)
    task_id = request.form.get("task_id", type=int)
    if task_id and repo().add_step(uid(), task_id, " ".join(note["body"].split())[:120]):
        repo().delete_note(uid(), note_id)
        say("note_moved_step")
        return redirect(url_for("zehava.tasks", open=task_id) + f"#task-{task_id}")
    say("choose_task", "warn")
    return back("zehava.notes")


@bp.route("/notes/<int:note_id>/to-snooze", methods=["POST"])
def note_to_snooze(note_id):
    note = owned_note(note_id)
    entry_id = repo().create_snooze_entry(uid(), note["body"])
    repo().delete_note(uid(), note_id)
    say("note_moved_snooze")
    return redirect(url_for("zehava.snooze", entry=entry_id) + "#thoughts")
