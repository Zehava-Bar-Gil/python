"""טיימר עגבנייה, מצב מיקוד וה-Soundscape. שני המסכים משתמשים באותו סשן, ולכן אין ספירה כפולה."""
from datetime import timedelta

from flask import abort, g, redirect, request, session, url_for

from .. import clock, focus_timer, journey, planner, security, ui
from . import back, bp, form_int, is_framed, page, repo, say, uid
from .task_views import task_options

SOUND_SPACES = ui.SOUND_SPACES
BREAK_OFFER_FOR = timedelta(minutes=15)   # כמה זמן אחרי סשן מציעים הפסקה


def default_minutes(kind):
    settings = g.settings
    return {"focus": settings["focus_minutes"], "short_break": settings["short_break_minutes"],
            "long_break": settings["long_break_minutes"]}[kind]


def form_task_id():
    task_id = request.form.get("task_id", type=int)
    return task_id if task_id and repo().get_task(uid(), task_id) else None


def start_session(kind, minutes, task_id=None):
    if focus_timer.start(repo(), uid(), kind, minutes, task_id) is None:
        say("already_running", "warn")


# ---------- טיימר עגבנייה ----------
@bp.route("/timer")
def timer():
    r, user_id, now = repo(), uid(), clock.now()
    state = focus_timer.state(r.active_session(user_id), now)
    suggest_break = None
    if not state["active"]:
        last = r.last_finished_session(user_id)
        if last and last["kind"] == "focus" and last["status"] == "completed" \
                and now - clock.from_iso(last["ended_at"]) < BREAK_OFFER_FOR:
            kind, minutes = focus_timer.break_suggestion(r, user_id, g.settings, now.date())
            suggest_break = {"kind": kind, "minutes": minutes}
    stats = focus_timer.day_stats(r, user_id, now.date())
    return page("zehava/timer.html", active="timer", timer=state,
                task=r.get_task(user_id, state["task_id"]) if state.get("task_id") else None,
                task_choices=task_options(), suggest_break=suggest_break, stats=stats,
                quick=focus_timer.QUICK_MINUTES, kinds=focus_timer.KINDS,
                defaults={kind: default_minutes(kind) for kind in focus_timer.KINDS},
                preselect=request.args.get("task", type=int))


@bp.route("/timer/start", methods=["POST"])
def timer_start():
    kind = request.form.get("kind")
    kind = kind if kind in focus_timer.KINDS else "focus"
    if kind != "focus":
        # להפסקות האורך מההגדרות. שדה הדקות בטופס שייך למיקוד
        start_session(kind, default_minutes(kind))
        return back("zehava.timer")
    flexible = request.form.get("flexible") == "1"
    minutes = 0 if flexible else form_int("minutes", default_minutes(kind), 1, 180)
    start_session(kind, minutes, form_task_id())
    return back("zehava.timer")


@bp.route("/timer/<int:minutes>", methods=["POST"])
def timer_quick(minutes):
    # כתובת מגרסה 1: התחלת מיקוד באורך מסוים בלחיצה אחת
    if not 1 <= minutes <= 180:
        abort(404)
    start_session("focus", minutes, form_task_id())
    return back("zehava.timer")


@bp.route("/timer/break/<kind>", methods=["POST"])
def timer_break(kind):
    if kind not in ("short_break", "long_break"):
        abort(404)
    start_session(kind, default_minutes(kind))
    return back("zehava.timer")


@bp.route("/timer/pause", methods=["POST"])
def timer_pause():
    focus_timer.pause(repo(), uid(), clock.now())
    return back("zehava.timer")


@bp.route("/timer/resume", methods=["POST"])
def timer_resume():
    focus_timer.resume(repo(), uid(), clock.now())
    return back("zehava.timer")


@bp.route("/timer/reset", methods=["POST"])
def timer_reset():
    # עצירה: הזמן שבוצע נשמר כפי שהוא, בלי עונש
    focus_timer.stop(repo(), uid(), clock.now())
    return back("zehava.timer")


# ---------- מצב מיקוד ----------
@bp.route("/focus")
def focus():
    r, user_id, now = repo(), uid(), clock.now()
    state = focus_timer.state(r.active_session(user_id), now)
    # טיימר פעיל קובע את המשימה. אחרת: המשימה שנבחרה, או הצעד הבא ברשימה
    task_id = state.get("task_id") or request.args.get("task", type=int)
    task = r.get_task(user_id, task_id) if task_id else None
    if not task or task["status"] != "open":
        task = planner.next_task(r.list_tasks(user_id)) if not state.get("task_id") else task
    if task:
        planner.attach_steps([task], r.steps_for_tasks(user_id, [task["id"]]))
    return page("zehava/focus.html", active="timer", timer=state, task=task,
                quick=[m for m in focus_timer.QUICK_MINUTES if m > 5])


@bp.route("/focus/start/<int:minutes>", methods=["POST"])
def focus_start(minutes):
    if not 0 <= minutes <= 180:
        abort(404)
    task_id = form_task_id()
    start_session("focus", minutes, task_id)
    return redirect(url_for("zehava.focus", task=task_id) if task_id else url_for("zehava.focus"))


@bp.route("/focus/done", methods=["POST"])
def focus_done():
    # "סיימתי את המשימה": הסשן נסגר עם הזמן שבוצע, והמשימה מסומנת כבוצעה
    focus_timer.stop(repo(), uid(), clock.now())
    task_id = form_task_id()
    if task_id and repo().set_task_done(uid(), task_id, True):
        journey.record(repo(), uid(), "task", task_id)
        say("task_done_note")
    return redirect(url_for("zehava.focus"))


@bp.route("/focus/leave", methods=["POST"])
def focus_leave():
    # יציאה בכל רגע. הזמן שכבר בוצע נרשם (בגרסה 1 הוא אבד)
    focus_timer.stop(repo(), uid(), clock.now())
    return redirect(url_for("zehava.home"))


# ---------- Soundscape ----------
@bp.route("/sounds")
def sounds():
    votes = repo().sound_feedback_counts(uid())
    liked = {key: v["yes"] - v["no"] for key, v in votes.items() if v["yes"]}
    return page("zehava/sounds.html", active="timer", spaces=SOUND_SPACES, votes=votes,
                favorite=max(liked, key=liked.get) if liked else None)


@bp.route("/sounds/vote/<space>/<answer>", methods=["POST"])
def sound_vote(space, answer):
    # 204: הדף לא נטען מחדש, אז המוזיקה ממשיכה לנגן
    if space in SOUND_SPACES and answer in ("yes", "no"):
        repo().add_sound_feedback(uid(), space, answer == "yes")
    return "", 204


# ---------- נגן שממשיך בין הדפים ----------
# בלי JavaScript, מעבר דף עוצר כל צליל. לכן הנגן הוא "מסגרת": הנגן הקטן נשאר בפינה,
# והאתר עצמו נטען בתוך iframe מתחתיו. כל קישור באתר מחליף רק את מה שבתוך המסגרת, והמוזיקה ממשיכה
def player_page(target):
    # רק דף של האתר, ולא הנגן עצמו (כדי שלא ייפתח נגן בתוך נגן)
    target = security.safe_next(target, "zehava.sounds")
    return url_for("zehava.sounds") if target.startswith("/zehava/listen") else target


@bp.route("/listen/<space>")
def listen(space):
    if space not in SOUND_SPACES:
        abort(404)
    page_inside = player_page(request.args.get("next"))
    if is_framed():
        # כבר בתוך הנגן: לא פותחים נגן נוסף, רק מחליפים את הדף
        return redirect(page_inside)
    session["playing"] = space
    return page("zehava/listen.html", space=space, sound_name=SOUND_SPACES[space], page_inside=page_inside)


@bp.route("/listen/stop", methods=["POST"])
def listen_stop():
    # עצירה: חוזרים לאותו דף, בלי הנגן
    session.pop("playing", None)
    return redirect(player_page(request.form.get("next")))
