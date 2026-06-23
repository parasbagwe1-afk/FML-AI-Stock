from app.models import (
    FIFOLayer,
    InterCompanyLedgerEntry,
    InterCompanyTransfer,
    OpeningStock,
    Payable,
    Payment,
    Receivable,
    StockLedgerEntry,
)
from tests.test_fifo_workflows import ids
from tests.test_navigation import login


def test_opening_page_hides_stock_book_and_rate_fields(client):
    login(client)
    response = client.get("/transactions/opening")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Stock book <select" not in html
    assert "Owner stock book" not in html
    assert "User stock book" not in html
    assert '<span>Rate</span>' not in html
    assert 'name="rate[]"' not in html


def test_opening_stock_saves_without_stock_book_or_rate(client, app):
    with app.app_context():
        data = ids()
        company_id = data["ai"].id
        item_id = data["item"].id

    login(client)
    response = client.post(
        "/transactions/opening/stock",
        data={
            "company_id": company_id,
            "reference_number": "OPEN-NO-RATE",
            "opening_date": "2026-06-22",
            "item_id[]": [item_id],
            "quantity[]": ["5"],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Opening stock OPEN-NO-RATE saved." in response.data

    with app.app_context():
        opening = OpeningStock.query.filter_by(reference_number="OPEN-NO-RATE").one()
        layer = FIFOLayer.query.filter_by(
            source_type="OPENING_STOCK",
            source_id=opening.id,
        ).one()
        assert opening.stock_book.code == "AI_GST"
        assert layer.unit_cost == 0
        assert layer.available_quantity == 5


def test_opening_stock_can_be_negative(client, app):
    with app.app_context():
        data = ids()
        company_id = data["ai"].id
        item_id = data["item"].id

    login(client)
    response = client.post(
        "/transactions/opening/stock",
        data={
            "company_id": company_id,
            "reference_number": "OPEN-NEGATIVE",
            "opening_date": "2026-06-22",
            "item_id[]": [item_id],
            "quantity[]": ["-2"],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Opening stock OPEN-NEGATIVE saved." in response.data

    with app.app_context():
        opening = OpeningStock.query.filter_by(reference_number="OPEN-NEGATIVE").one()
        ledger = StockLedgerEntry.query.filter_by(
            transaction_type="OPENING_STOCK",
            transaction_id=opening.id,
        ).one()
        assert opening.lines[0].quantity == -2
        assert ledger.quantity_in == 0
        assert ledger.quantity_out == 2
        assert FIFOLayer.query.filter_by(source_type="OPENING_STOCK", source_id=opening.id).count() == 0


def test_opening_pending_stock_saves_without_stock_books_or_rate(client, app):
    with app.app_context():
        data = ids()
        owner_id = data["fml"].id
        user_id = data["ai"].id
        item_id = data["item"].id

    login(client)
    response = client.post(
        "/transactions/opening/pending-stock",
        data={
            "from_company_id": owner_id,
            "to_company_id": user_id,
            "reference_number": "PEND-NO-RATE",
            "transfer_date": "2026-06-22",
            "item_id[]": [item_id],
            "quantity[]": ["3"],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Opening pending stock PEND-NO-RATE saved." in response.data

    with app.app_context():
        transfer = InterCompanyTransfer.query.filter_by(reference_number="PEND-NO-RATE").one()
        assert transfer.from_stock_book.code == "FML_GST"
        assert transfer.to_stock_book.code == "AI_GST"
        assert transfer.lines[0].fifo_value == 0


def test_opening_pending_stock_can_be_negative(client, app):
    with app.app_context():
        data = ids()
        owner_id = data["fml"].id
        user_id = data["ai"].id
        item_id = data["item"].id

    login(client)
    response = client.post(
        "/transactions/opening/pending-stock",
        data={
            "from_company_id": owner_id,
            "to_company_id": user_id,
            "reference_number": "PEND-NEGATIVE",
            "transfer_date": "2026-06-22",
            "item_id[]": [item_id],
            "quantity[]": ["-3"],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Opening pending stock PEND-NEGATIVE saved." in response.data

    with app.app_context():
        transfer = InterCompanyTransfer.query.filter_by(reference_number="PEND-NEGATIVE").one()
        ledger = InterCompanyLedgerEntry.query.filter_by(transfer_id=transfer.id).one()
        assert transfer.lines[0].quantity == -3
        assert transfer.lines[0].fifo_value == 0
        assert ledger.quantity == -3


def test_opening_summary_can_delete_receivable_payable_and_advance(client, app):
    with app.app_context():
        data = ids()
        company_id = data["ai"].id
        customer_id = data["customer"].id
        supplier_id = data["supplier"].id

    login(client)
    client.post(
        "/transactions/opening/receivable",
        data={
            "company_id": company_id,
            "customer_id": customer_id,
            "sale_type": "GST",
            "reference_number": "OPEN-REC-DELETE",
            "invoice_date": "2026-06-22",
            "due_date": "2026-06-30",
            "pending_amount": "78440",
        },
        follow_redirects=True,
    )
    client.post(
        "/transactions/opening/payable",
        data={
            "company_id": company_id,
            "supplier_id": supplier_id,
            "purchase_type": "GST",
            "reference_number": "OPEN-PAY-DELETE",
            "bill_date": "2026-06-22",
            "due_date": "2026-06-30",
            "pending_amount": "12500",
        },
        follow_redirects=True,
    )
    client.post(
        "/transactions/opening/advance-received",
        data={
            "company_id": company_id,
            "customer_id": customer_id,
            "payment_date": "2026-06-22",
            "mode": "CASH",
            "reference_number": "OPEN-ADV-DELETE",
            "amount": "5000",
        },
        follow_redirects=True,
    )

    response = client.get("/transactions/opening")
    html = response.get_data(as_text=True)
    assert "/transactions/opening/receivable/" in html
    assert "/transactions/opening/payable/" in html
    assert "/transactions/opening/advance/" in html

    with app.app_context():
        receivable = Receivable.query.filter_by(document_number="OPEN-REC-DELETE").one()
        payable = Payable.query.filter_by(document_number="OPEN-PAY-DELETE").one()
        payment = Payment.query.filter_by(reference_number="OPEN-ADV-DELETE").one()
        receivable_id = receivable.id
        payable_id = payable.id
        payment_id = payment.id

    response = client.post(
        f"/transactions/opening/receivable/{receivable_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Opening receivable deleted." in response.data

    response = client.post(
        f"/transactions/opening/payable/{payable_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Opening payable deleted." in response.data

    response = client.post(
        f"/transactions/opening/advance/{payment_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Opening advance deleted." in response.data

    with app.app_context():
        assert Receivable.query.filter_by(document_number="OPEN-REC-DELETE").count() == 0
        assert Payable.query.filter_by(document_number="OPEN-PAY-DELETE").count() == 0
        assert Payment.query.filter_by(reference_number="OPEN-ADV-DELETE").count() == 0
