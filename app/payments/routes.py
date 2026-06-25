from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.core.company_context import active_company
from app.core.formatting import money
from app.core.security import require_permission
from app.extensions import db
from app.models import Company, Customer, Payable, Payment, PaymentMode, Receivable, Supplier
from app.services.entry_exports import export_entry, payment_rows
from app.services.outstanding import grouped_party_outstanding
from app.services.payments import create_customer_receipt, create_supplier_payment

bp = Blueprint("payments", __name__, url_prefix="/finance")


def finance_options():
    company = active_company()
    companies = Company.query.filter_by(active=True)
    receivables = Receivable.query.filter(Receivable.balance_amount > 0)
    payables = Payable.query.filter(Payable.balance_amount > 0)
    if company:
        companies = companies.filter(Company.id == company.id)
        receivables = receivables.filter(Receivable.company_id == company.id)
        payables = payables.filter(Payable.company_id == company.id)
    return {
        "companies": companies.order_by(Company.code).all(),
        "customers": Customer.query.filter_by(active=True).order_by(Customer.code).all(),
        "suppliers": Supplier.query.filter_by(active=True).order_by(Supplier.code).all(),
        "payment_modes": PaymentMode.query.filter_by(active=True).order_by(PaymentMode.code).all(),
        "receivables": receivables.order_by(Receivable.due_date, Receivable.document_number).all(),
        "payables": payables.order_by(Payable.due_date, Payable.document_number).all(),
    }


def require_active_company_value(company_id):
    company = active_company()
    if company and str(company_id or "") != str(company.id):
        raise ValueError("This login can record payments only for the active company.")


def require_active_company_document(company_id):
    company = active_company()
    if company and str(company_id or "") != str(company.id):
        abort(403)


def receivable_edit_url(receivable):
    if receivable.source_type == "SALE":
        return url_for("transactions.sale_edit", sale_id=receivable.source_id)
    if receivable.source_type == "OPENING_RECEIVABLE":
        return url_for("transactions.opening_receivable_edit", receivable_id=receivable.id)
    return None


def payable_edit_url(payable):
    if payable.source_type == "PURCHASE":
        return url_for("transactions.purchase_edit", purchase_id=payable.source_id)
    if payable.source_type == "OPENING_PAYABLE":
        return url_for("transactions.opening_payable_edit", payable_id=payable.id)
    return None


def receivable_detail_rows(company_id, customer_id):
    rows = (
        Receivable.query.filter_by(company_id=company_id, customer_id=customer_id)
        .order_by(Receivable.document_date, Receivable.document_number, Receivable.id)
        .all()
    )
    return [
        {
            "document": row.document_number,
            "date": row.document_date,
            "due_date": row.due_date,
            "type": row.transaction_type or row.source_type,
            "source": "Opening" if row.is_opening else row.source_type.title(),
            "total": row.total_amount,
            "paid": row.paid_amount,
            "balance": row.balance_amount,
            "status": row.payment_status,
            "remarks": row.remarks or "",
            "edit_url": receivable_edit_url(row),
        }
        for row in rows
    ]


def payable_detail_rows(company_id, supplier_id):
    rows = (
        Payable.query.filter_by(company_id=company_id, supplier_id=supplier_id)
        .order_by(Payable.document_date, Payable.document_number, Payable.id)
        .all()
    )
    return [
        {
            "document": row.document_number,
            "date": row.document_date,
            "due_date": row.due_date,
            "type": row.transaction_type or row.source_type,
            "source": "Opening" if row.is_opening else row.source_type.title(),
            "total": row.total_amount,
            "paid": row.paid_amount,
            "balance": row.balance_amount,
            "status": row.payment_status,
            "remarks": row.remarks or "",
            "edit_url": payable_edit_url(row),
        }
        for row in rows
    ]


@bp.route("/payments", methods=["GET"])
@login_required
@require_permission("payments", "view")
def index():
    recent_payments = Payment.query
    company = active_company()
    if company:
        recent_payments = recent_payments.filter(Payment.company_id == company.id)
    recent_payments = recent_payments.order_by(Payment.payment_date.desc(), Payment.id.desc()).limit(30).all()
    return render_template("payments/index.html", recent_payments=recent_payments, **finance_options())


@bp.route("/payments/<int:payment_id>/export/<fmt>")
@login_required
@require_permission("payments", "view")
def payment_export(payment_id, fmt):
    payment = db.session.get(Payment, payment_id)
    if not payment:
        abort(404)
    require_active_company_document(payment.company_id)
    try:
        title, rows = payment_rows(payment)
        return export_entry(title, rows, fmt)
    except ValueError:
        abort(404)


@bp.route("/payments/customer-receipt", methods=["POST"])
@login_required
@require_permission("payments", "create")
def customer_receipt():
    try:
        require_active_company_value(request.form.get("company_id"))
        payment = create_customer_receipt(request.form, current_user)
        db.session.commit()
        flash(f"Customer receipt for {payment.total_amount} saved.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("payments.index"))


@bp.route("/payments/supplier-payment", methods=["POST"])
@login_required
@require_permission("payments", "create")
def supplier_payment():
    try:
        require_active_company_value(request.form.get("company_id"))
        payment = create_supplier_payment(request.form, current_user)
        db.session.commit()
        flash(f"Supplier payment for {payment.total_amount} saved.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("payments.index"))


@bp.route("/outstanding")
@login_required
@require_permission("outstanding", "view")
def outstanding():
    company = active_company()
    company_id = company.id if company else request.args.get("company_id")
    status = request.args.get("status")
    search = (request.args.get("q") or "").strip()
    receivables = Receivable.query
    payables = Payable.query
    if company_id:
        receivables = receivables.filter_by(company_id=company_id)
        payables = payables.filter_by(company_id=company_id)
    if status:
        receivables = receivables.filter_by(payment_status=status)
        payables = payables.filter_by(payment_status=status)
    if search:
        pattern = f"%{search}%"
        receivables = receivables.outerjoin(Customer, Receivable.customer_id == Customer.id).filter(
            db.or_(
                Receivable.document_number.ilike(pattern),
                Customer.code.ilike(pattern),
                Customer.name.ilike(pattern),
            )
        )
        payables = payables.outerjoin(Supplier, Payable.supplier_id == Supplier.id).filter(
            db.or_(
                Payable.document_number.ilike(pattern),
                Supplier.code.ilike(pattern),
                Supplier.name.ilike(pattern),
            )
        )
    receivable_entries = receivables.order_by(Receivable.due_date, Receivable.document_date).all()
    payable_entries = payables.order_by(Payable.due_date, Payable.document_date).all()
    receivables = grouped_party_outstanding(receivable_entries, "customer")
    payables = grouped_party_outstanding(payable_entries, "supplier")
    advances = Payment.query.filter(Payment.unallocated_amount > 0)
    companies = Company.query.filter_by(active=True)
    if company:
        advances = advances.filter(Payment.company_id == company.id)
        companies = companies.filter(Company.id == company.id)
    if search:
        pattern = f"%{search}%"
        advances = advances.outerjoin(Customer, Payment.customer_id == Customer.id).outerjoin(
            Supplier, Payment.supplier_id == Supplier.id
        ).filter(
            db.or_(
                Payment.reference_number.ilike(pattern),
                Payment.payment_type.ilike(pattern),
                Payment.mode.ilike(pattern),
                Customer.code.ilike(pattern),
                Customer.name.ilike(pattern),
                Supplier.code.ilike(pattern),
                Supplier.name.ilike(pattern),
            )
        )
    advances = advances.order_by(Payment.payment_date.desc()).all()
    summary = {
        "receivable_balance": money(sum((row["balance"] for row in receivables), 0)),
        "payable_balance": money(sum((row["balance"] for row in payables), 0)),
        "advance_unallocated": money(sum((row.unallocated_amount for row in advances), 0)),
        "receivable_count": len(receivables),
        "payable_count": len(payables),
        "advance_count": len(advances),
        "search": search,
    }
    return render_template(
        "payments/outstanding.html",
        receivables=receivables,
        payables=payables,
        advances=advances,
        summary=summary,
        companies=companies.order_by(Company.code).all(),
    )


@bp.route("/outstanding/customer/<int:company_id>/<int:customer_id>")
@login_required
@require_permission("outstanding", "view")
def outstanding_customer_detail(company_id, customer_id):
    require_active_company_document(company_id)
    company = db.session.get(Company, company_id)
    customer = db.session.get(Customer, customer_id)
    if not company or not customer:
        abort(404)
    rows = receivable_detail_rows(company_id, customer_id)
    summary = {
        "total": money(sum((row["total"] for row in rows), 0)),
        "paid": money(sum((row["paid"] for row in rows), 0)),
        "balance": money(sum((row["balance"] for row in rows), 0)),
        "count": len(rows),
    }
    return render_template(
        "payments/outstanding_detail.html",
        title="Customer Outstanding Details",
        party_label="Customer",
        party_name=customer.name,
        company=company,
        rows=rows,
        summary=summary,
        back_url=url_for("payments.outstanding"),
    )


@bp.route("/outstanding/supplier/<int:company_id>/<int:supplier_id>")
@login_required
@require_permission("outstanding", "view")
def outstanding_supplier_detail(company_id, supplier_id):
    require_active_company_document(company_id)
    company = db.session.get(Company, company_id)
    supplier = db.session.get(Supplier, supplier_id)
    if not company or not supplier:
        abort(404)
    rows = payable_detail_rows(company_id, supplier_id)
    summary = {
        "total": money(sum((row["total"] for row in rows), 0)),
        "paid": money(sum((row["paid"] for row in rows), 0)),
        "balance": money(sum((row["balance"] for row in rows), 0)),
        "count": len(rows),
    }
    return render_template(
        "payments/outstanding_detail.html",
        title="Supplier Outstanding Details",
        party_label="Supplier",
        party_name=supplier.name,
        company=company,
        rows=rows,
        summary=summary,
        back_url=url_for("payments.outstanding"),
    )
