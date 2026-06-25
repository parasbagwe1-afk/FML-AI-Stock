from app.extensions import db
from app.models import Payment, PaymentAllocation, Receivable, Sale
from app.services.payments import create_customer_receipt
from app.services.transactions import create_sale
from tests.test_fifo_workflows import admin, ids
from tests.test_navigation import login


def create_receipt_fixture():
    data = ids()
    sale = create_sale(
        {
            "company_id": data["ai"].id,
            "stock_book_id": data["ai_gst"].id,
            "customer_id": data["customer"].id,
            "sale_type": "GST",
            "invoice_number": "PAY-EDIT-INV",
            "invoice_date": "2026-06-25",
        },
        [{"item_id": data["item"].id, "quantity": "1", "rate": "100", "gst_percent": "18"}],
        admin(),
    )
    receivable = Receivable.query.filter_by(document_number="PAY-EDIT-INV").one()
    payment = create_customer_receipt(
        {
            "company_id": data["ai"].id,
            "customer_id": data["customer"].id,
            "receivable_id": receivable.id,
            "payment_date": "2026-06-25",
            "amount": "50",
            "mode": "UPI",
            "reference_number": "PAY-EDIT-REF",
        },
        admin(),
    )
    db.session.commit()
    return payment.id, receivable.id, sale.id, data["ai"].id, data["customer"].id


def test_payment_page_exposes_edit_and_delete_actions(client, app):
    with app.app_context():
        payment_id, *_ = create_receipt_fixture()

    login(client)
    response = client.get("/finance/payments")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert f"/finance/payments/{payment_id}/edit" in html
    assert f"/finance/payments/{payment_id}/delete" in html
    assert "Delete this payment and reverse its allocation?" in html


def test_payment_edit_recalculates_allocation_and_sale_balance(client, app):
    with app.app_context():
        payment_id, receivable_id, sale_id, company_id, customer_id = create_receipt_fixture()

    login(client)
    edit_page = client.get(f"/finance/payments/{payment_id}/edit")
    assert edit_page.status_code == 200
    assert b"Edit Payment" in edit_page.data

    response = client.post(
        f"/finance/payments/{payment_id}/edit",
        data={
            "company_id": company_id,
            "customer_id": customer_id,
            "receivable_id": receivable_id,
            "payment_date": "2026-06-26",
            "mode": "BANK",
            "reference_number": "PAY-EDIT-UPDATED",
            "amount": "75",
            "remarks": "Corrected amount",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Payment updated and allocation recalculated." in response.data

    with app.app_context():
        payment = db.session.get(Payment, payment_id)
        receivable = db.session.get(Receivable, receivable_id)
        sale = db.session.get(Sale, sale_id)
        assert payment.total_amount == 75
        assert payment.allocated_amount == 75
        assert payment.unallocated_amount == 0
        assert payment.mode == "BANK"
        assert payment.reference_number == "PAY-EDIT-UPDATED"
        assert receivable.paid_amount == 75
        assert receivable.balance_amount == 43
        assert sale.paid_amount == 75
        assert sale.balance_amount == 43
        assert PaymentAllocation.query.filter_by(payment_id=payment_id).count() == 1


def test_payment_delete_reverses_allocation(client, app):
    with app.app_context():
        payment_id, receivable_id, sale_id, *_ = create_receipt_fixture()

    login(client)
    response = client.post(f"/finance/payments/{payment_id}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Payment deleted and allocation reversed." in response.data

    with app.app_context():
        receivable = db.session.get(Receivable, receivable_id)
        sale = db.session.get(Sale, sale_id)
        assert db.session.get(Payment, payment_id) is None
        assert PaymentAllocation.query.filter_by(payment_id=payment_id).count() == 0
        assert receivable.paid_amount == 0
        assert receivable.balance_amount == 118
        assert sale.paid_amount == 0
        assert sale.balance_amount == 118
