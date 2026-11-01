"""הרשמה, כניסה, יציאה, אימות מייל, איפוס סיסמה, שפה ודף הפרטיות."""
from datetime import timedelta

from flask import current_app, g, redirect, request, session, url_for

from .. import accounts, clock, mailer, security
from . import back, bp, current_lang, page, repo, say, say_password_level, uid

MAX_ACCOUNT_EMAILS_PER_HOUR = 3


def _send_account_email(user, kind, endpoint):
    # שולח מייל אימות או איפוס, עם הגבלה של 3 בשעה לכל חשבון
    since = clock.to_iso(clock.now() - timedelta(hours=1))
    if repo().count_emails(user["id"], kind, since) >= MAX_ACCOUNT_EMAILS_PER_HOUR:
        return "limited"
    token = accounts.verification_token(user) if kind == "verify" else accounts.reset_token(user)
    app = current_app._get_current_object()
    link = mailer.external_url(app, endpoint, token=token)
    return "sent" if mailer.send_account_email(app, repo(), user, kind, current_lang(), link) else "failed"


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("zehava.home"))
    error = None
    email = ""
    if request.method == "POST":
        email = accounts.normalize_email(request.form.get("email"))
        user, error = accounts.authenticate(repo(), email, request.form.get("password", ""), security.client_ip())
        if user:
            security.login_user(user)
            return redirect(security.safe_next(request.form.get("next")))
    return page("zehava/login.html", error=error, email=email, next=request.values.get("next", ""))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("zehava.home"))
    errors, form = [], {"email": "", "name": ""}
    if request.method == "POST":
        form = {"email": request.form.get("email", ""), "name": request.form.get("name", "")}
        user_id, errors = accounts.register(repo(), form["email"], form["name"], request.form.get("password", ""),
                                            current_lang())
        if user_id:
            user = repo().get_user(user_id)
            security.login_user(user)
            g.user, g.settings = user, repo().get_settings(user_id)
            say("welcome")
            say_password_level(request.form.get("password", ""), user["email"])
            if _send_account_email(user, "verify", "zehava.verify") == "sent":
                say("verify_sent")
            return redirect(url_for("zehava.home"))
    return page("zehava/register.html", errors=errors, form=form)


@bp.route("/logout", methods=["POST"])
def logout():
    security.logout_user()
    return redirect(url_for("zehava.login"))


@bp.route("/verify/<token>")
def verify(token):
    ok = accounts.confirm_verification(repo(), token)
    return page("zehava/message.html", title_key="verify_ok" if ok else "verify_bad", ok=ok)


@bp.route("/verify/resend", methods=["POST"])
def verify_resend():
    if g.user["email_verified_at"]:
        say("verify_ok")
    else:
        result = _send_account_email(g.user, "verify", "zehava.verify")
        say({"sent": "verify_sent", "limited": "err_too_many", "failed": "mail_error"}[result],
            "ok" if result == "sent" else "warn")
    # אחרי לחיצה על הקישור ההתראה בדף הבית נעלמת, עד היציאה מהחשבון. אפשר לשלוח שוב מההגדרות
    session["verify_banner_hidden"] = True
    return back("zehava.settings")


@bp.route("/forgot", methods=["GET", "POST"])
def forgot():
    sent = False
    if request.method == "POST":
        user = repo().get_user_by_email(accounts.normalize_email(request.form.get("email")))
        if user:
            _send_account_email(user, "reset", "zehava.reset")
        # אותה תשובה בכל מקרה, כדי לא לחשוף אם יש חשבון עם המייל הזה
        sent = True
    return page("zehava/forgot.html", sent=sent)


@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset(token):
    if not accounts.user_for_reset(repo(), token):
        return page("zehava/message.html", title_key="reset_bad", ok=False), 400
    errors = []
    if request.method == "POST":
        errors = accounts.reset_password(repo(), token, request.form.get("password", ""))
        if not errors:
            security.logout_user()
            say("reset_ok")
            say_password_level(request.form.get("password", ""))
            return redirect(url_for("zehava.login"))
    return page("zehava/reset.html", errors=errors, token=token)


@bp.route("/lang/<code>", methods=["POST"])
def lang(code):
    if code in ("he", "en"):
        if g.user:
            repo().update_settings(uid(), lang=code)
        else:
            session["lang"] = code
    return back("zehava.home")


@bp.route("/privacy")
def privacy():
    return page("zehava/privacy.html")
