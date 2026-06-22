from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.core.company_context import active_company
from app.core.forms import item_lines_from_form, transfer_lines_from_form
from app.core.security import can, require_permission
from app.extensions import db
from app.models import (
    Company,
    Customer,
    InterCompanyTransfer,
    Item,
    OpeningStock,
    Payable,
    Payment,
    PaymentMode,
    Purchase,
    Receivable,
    Sale,
    StockBook,
    Supplier,
)
from app.services.references import next_reference
from app.services.transactions import (
    create_opening_advance_paid,
    create_opening_advance_received,
    create_opening_payable,
    create_opening_pending_stock,
    create_opening_receivable,
    create_opening_stock,
    create_purchase,
    create_sale,
    create_transfer,
    pending_transfer_summary,
    update_purchase_header,
    update_purchase_lines,
    update_sale_header,
    update_sale_lines,
    update_transfer_header,
    void_opening_stock,
    void_purchase,
    void_sale,
    void_transfer,
)

bp = Blueprint("transactions", __name__, url_prefix="/transactions")


def options():
    return {
        "companies": Company.query.filter_by(active=True).order_by(Company.code).all(),
        "stock_books": StockBook.query.filter_by(active=True).order_by(StockBook.code).all(),
        "items": Item.query.filter_by(active=True).order_by(Item.code).all(),
        "suppliers": Supplier.query.filter_by(active=True).order_by(Supplier.code).all(),
        "customers": Customer.query.filter_by(active=True).order_by(Customer.code).all(),
        "payment_modes": PaymentMode.query.filter_by(active=True).order_by(PaymentMode.code).all(),
    }


def active_company_id():
    company = active_company()
    return company.id if company else None


@bp.route("/reference/<kind>")
@login_required
def reference(kind):
    return jsonify({"reference": next_reference(kind)})


@bp.route("/purchase", methods=["GET", "POST"])
@login_required
@require_permission("purchase", "view")
def purchase():
    if request.method == "POST":
        require_permission("purchase", "create")(lambda: None)()
        try:
            purchase = create_purchase(request.form, item_lines_from_form(request.form), current_user)
            db.session.commit()
            flash(f"Purchase {purchase.bill_number} saved.", "success")
            return redirect(url_for("transactions.purchase"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    purchases = Purchase.query.filter_by(is_void=False)
    company_id = active_company_id()
    if company_id:
        purchases = purchases.filter(Purchase.company_id == company_id)
    purchases = purchases.order_by(Purchase.bill_date.desc(), Purchase.id.desc()).limit(20).all()
    return render_template("transactions/purchase.html", purchases=purchases, **options())


@bp.route("/purchase/<int:purchase_id>/edit", methods=["GET", "POST"])
@login_required
def purchase_edit(purchase_id):
    if not (can(current_user, "purchase", "edit") or can(current_user, "purchase", "create")):
        abort(403)
    purchase = db.session.get(Purchase, purchase_id)
    if not purchase:
        flash("Purchase not found.", "danger")
        return redirect(url_for("transactions.purchase"))
    if request.method == "POST":
        try:
            update_purchase_header(purchase, request.form, current_user)
            update_purchase_lines(purchase, item_lines_from_form(request.form), request.form, current_user)
            db.session.commit()
            flash(f"Purchase {purchase.bill_number} updated.", "success")
            return redirect(url_for("transactions.purchase"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    return render_template("transactions/purchase_edit.html", purchase=purchase, **options())


@bp.route("/purchase/<int:purchase_id>/delete", methods=["POST"])
@login_required
def purchase_delete(purchase_id):
    if not (can(current_user, "purchase", "edit") or can(current_user, "purchase", "deactivate")):
        abort(403)
    purchase = db.session.get(Purchase, purchase_id)
    if not purchase:
        flash("Purchase not found.", "danger")
        return redirect(url_for("transactions.purchase"))
    try:
        void_purchase(purchase, current_user)
        db.session.commit()
        flash("Purchase deleted and stock reversed.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("transactions.purchase"))


@bp.route("/sale", methods=["GET", "POST"])
@login_required
@require_permission("sale", "view")
def sale():
    if request.method == "POST":
        require_permission("sale", "create")(lambda: None)()
        try:
            sale = create_sale(request.form, item_lines_from_form(request.form), current_user)
            db.session.commit()
            flash(f"Sale {sale.invoice_number} saved.", "success")
            return redirect(url_for("transactions.sale"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    sales = Sale.query.filter_by(is_void=False)
    company_id = active_company_id()
    if company_id:
        sales = sales.filter(Sale.company_id == company_id)
    sales = sales.order_by(Sale.invoice_date.desc(), Sale.id.desc()).limit(20).all()
    return render_template("transactions/sale.html", sales=sales, **options())


@bp.route("/sale/<int:sale_id>/edit", methods=["GET", "POST"])
@login_required
def sale_edit(sale_id):
    if not (can(current_user, "sale", "edit") or can(current_user, "sale", "create")):
        abort(403)
    sale = db.session.get(Sale, sale_id)
    if not sale:
        flash("Sale not found.", "danger")
        return redirect(url_for("transactions.sale"))
    if request.method == "POST":
        try:
            update_sale_header(sale, request.form, current_user)
            update_sale_lines(sale, item_lines_from_form(request.form), current_user)
            db.session.commit()
            flash(f"Sale {sale.invoice_number} updated.", "success")
            return redirect(url_for("transactions.sale"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    return render_template("transactions/sale_edit.html", sale=sale, **options())


@bp.route("/sale/<int:sale_id>/delete", methods=["POST"])
@login_required
def sale_delete(sale_id):
    if not (can(current_user, "sale", "edit") or can(current_user, "sale", "deactivate")):
        abort(403)
    sale = db.session.get(Sale, sale_id)
    if not sale:
        flash("Sale not found.", "danger")
        return redirect(url_for("transactions.sale"))
    try:
        void_sale(sale, current_user)
        db.session.commit()
        flash("Sale deleted and stock restored.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("transactions.sale"))


@bp.route("/transfer", methods=["GET", "POST"])
@login_required
@require_permission("transfer", "view")
def transfer():
    if request.method == "POST":
        require_permission("transfer", "create")(lambda: None)()
        try:
            transfer = create_transfer(request.form, transfer_lines_from_form(request.form), current_user)
            db.session.commit()
            flash(f"Transfer {transfer.reference_number} saved.", "success")
            return redirect(url_for("transactions.transfer"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    transfers = InterCompanyTransfer.query.filter_by(is_void=False)
    company_id = active_company_id()
    if company_id:
        transfers = transfers.filter(
            db.or_(
                InterCompanyTransfer.from_company_id == company_id,
                InterCompanyTransfer.to_company_id == company_id,
            )
        )
    transfers = transfers.order_by(InterCompanyTransfer.transfer_date.desc(), InterCompanyTransfer.id.desc()).limit(20).all()
    return render_template(
        "transactions/transfer.html",
        transfers=transfers,
        pending_rows=pending_transfer_summary(),
        **options(),
    )


@bp.route("/transfer/<int:transfer_id>/edit", methods=["GET", "POST"])
@login_required
def transfer_edit(transfer_id):
    if not (can(current_user, "transfer", "edit") or can(current_user, "transfer", "create")):
        abort(403)
    transfer = db.session.get(InterCompanyTransfer, transfer_id)
    if not transfer:
        flash("Transfer not found.", "danger")
        return redirect(url_for("transactions.transfer"))
    if request.method == "POST":
        try:
            update_transfer_header(transfer, request.form, current_user)
            db.session.commit()
            flash(f"Transfer {transfer.reference_number} updated.", "success")
            return redirect(url_for("transactions.transfer"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    return render_template("transactions/transfer_edit.html", transfer=transfer, **options())


@bp.route("/transfer/<int:transfer_id>/delete", methods=["POST"])
@login_required
def transfer_delete(transfer_id):
    if not (can(current_user, "transfer", "edit") or can(current_user, "transfer", "deactivate")):
        abort(403)
    transfer = db.session.get(InterCompanyTransfer, transfer_id)
    if not transfer:
        flash("Transfer not found.", "danger")
        return redirect(url_for("transactions.transfer"))
    try:
        void_transfer(transfer, current_user)
        db.session.commit()
        flash("Transfer deleted and stock movement reversed.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("transactions.transfer"))


@bp.route("/opening", methods=["GET"])
@login_required
@require_permission("opening", "view")
def opening():
    company_id = active_company_id()
    opening_stock = OpeningStock.query.filter_by(is_void=False)
    receivables = Receivable.query.filter_by(is_opening=True)
    payables = Payable.query.filter_by(is_opening=True)
    advances = Payment.query.filter(Payment.payment_type.like("OPENING_ADVANCE%"))
    if company_id:
        opening_stock = opening_stock.filter(OpeningStock.company_id == company_id)
        receivables = receivables.filter(Receivable.company_id == company_id)
        payables = payables.filter(Payable.company_id == company_id)
        advances = advances.filter(Payment.company_id == company_id)
    return render_template(
        "transactions/opening.html",
        opening_stock=opening_stock.order_by(OpeningStock.opening_date.desc()).limit(20).all(),
        receivables=receivables.order_by(Receivable.document_date.desc()).limit(20).all(),
        payables=payables.order_by(Payable.document_date.desc()).limit(20).all(),
        advances=advances.order_by(Payment.payment_date.desc()).limit(20).all(),
        **options(),
    )


@bp.route("/opening/<section>", methods=["POST"])
@login_required
@require_permission("opening", "create")
def opening_save(section):
    try:
        if section == "stock":
            record = create_opening_stock(request.form, item_lines_from_form(request.form), current_user)
            message = f"Opening stock {record.reference_number} saved."
        elif section == "receivable":
            record = create_opening_receivable(request.form, current_user)
            message = f"Opening receivable {record.document_number} saved."
        elif section == "pending-stock":
            record = create_opening_pending_stock(request.form, item_lines_from_form(request.form), current_user)
            message = f"Opening pending stock {record.reference_number} saved."
        elif section == "payable":
            record = create_opening_payable(request.form, current_user)
            message = f"Opening payable {record.document_number} saved."
        elif section == "advance-received":
            record = create_opening_advance_received(request.form, current_user)
            message = "Opening advance received saved."
        elif section == "advance-paid":
            record = create_opening_advance_paid(request.form, current_user)
            message = "Opening advance paid saved."
        else:
            flash("Unknown opening section.", "danger")
            return redirect(url_for("transactions.opening"))
        db.session.commit()
        flash(message, "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("transactions.opening"))


@bp.route("/opening/stock/<int:opening_id>/delete", methods=["POST"])
@login_required
def opening_stock_delete(opening_id):
    if not (can(current_user, "opening", "create") or can(current_user, "opening", "deactivate")):
        abort(403)
    opening = db.session.get(OpeningStock, opening_id)
    if not opening:
        flash("Opening stock not found.", "danger")
        return redirect(url_for("transactions.opening"))
    try:
        void_opening_stock(opening, current_user)
        db.session.commit()
        flash("Opening stock deleted and stock reversed.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("transactions.opening"))
