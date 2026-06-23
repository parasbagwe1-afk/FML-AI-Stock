from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.core.company_context import clear_active_company, company_choices, set_active_company, set_active_company_for_user, user_can_view_all_companies

bp = Blueprint("company", __name__, url_prefix="/company")


def safe_next_url(value):
    if value:
        parsed = urlparse(value)
        if not parsed.netloc and not parsed.scheme and value.startswith("/"):
            return value
    return url_for("dashboard.index")


@bp.route("/choose", methods=["GET"])
@login_required
def choose():
    fixed_company = set_active_company_for_user(current_user)
    if fixed_company:
        return redirect(safe_next_url(request.args.get("next")))
    if user_can_view_all_companies(current_user) and request.args.get("all") == "1":
        clear_active_company()
        return redirect(safe_next_url(request.args.get("next")))
    return render_template(
        "company/choose.html",
        companies=company_choices(),
        next_url=safe_next_url(request.args.get("next")),
    )


@bp.route("/select", methods=["POST"])
@login_required
def select():
    fixed_company = set_active_company_for_user(current_user)
    if fixed_company:
        return redirect(safe_next_url(request.form.get("next")))
    company = set_active_company(request.form.get("company_id"))
    if not company:
        flash("Please choose an active company.", "danger")
        return redirect(url_for("company.choose", next=safe_next_url(request.form.get("next"))))
    flash(f"Using {company.name}.", "success")
    return redirect(safe_next_url(request.form.get("next")))


@bp.route("/all", methods=["POST"])
@login_required
def all_companies():
    if not user_can_view_all_companies(current_user):
        return redirect(safe_next_url(request.form.get("next")))
    clear_active_company()
    flash("Showing combined FirstTech and Aditya data.", "success")
    return redirect(safe_next_url(request.form.get("next")))
