from app.extensions import db
from app.models import FIFOLayer, Payable, Purchase, StockLedgerEntry
from app.services.transactions import create_purchase, update_purchase_header
from tests.test_fifo_workflows import admin, ids


def test_purchase_header_edit_updates_linked_references(app):
    with app.app_context():
        data = ids()
        purchase = create_purchase(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "supplier_id": data["supplier"].id,
                "purchase_type": "GST",
                "bill_number": "OLD-BILL",
                "bill_date": "2026-06-01",
                "due_date": "2026-06-15",
            },
            [{"item_id": data["item"].id, "quantity": "2", "rate": "100", "gst_percent": "18"}],
            admin(),
        )
        db.session.flush()

        update_purchase_header(
            purchase,
            {
                "supplier_id": data["supplier"].id,
                "bill_number": "NEW-BILL",
                "bill_date": "2026-06-02",
                "due_date": "2026-06-20",
                "remarks": "Corrected bill details",
            },
            admin(),
        )
        db.session.commit()

        purchase = Purchase.query.filter_by(bill_number="NEW-BILL").one()
        payable = Payable.query.filter_by(source_type="PURCHASE", source_id=purchase.id).one()
        layer = FIFOLayer.query.filter_by(source_type="PURCHASE", source_id=purchase.id).one()
        ledger = StockLedgerEntry.query.filter_by(
            transaction_type="PURCHASE", transaction_id=purchase.id
        ).one()

        assert purchase.remarks == "Corrected bill details"
        assert payable.document_number == "NEW-BILL"
        assert str(payable.due_date) == "2026-06-20"
        assert layer.source_reference == "NEW-BILL"
        assert str(layer.source_date) == "2026-06-02"
        assert ledger.reference_number == "NEW-BILL"
        assert str(ledger.entry_date) == "2026-06-02"


def test_purchase_edit_page_renders(client, app):
    with app.app_context():
        data = ids()
        purchase = create_purchase(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "supplier_id": data["supplier"].id,
                "purchase_type": "GST",
                "bill_number": "UI-BILL",
                "bill_date": "2026-06-01",
            },
            [{"item_id": data["item"].id, "quantity": "1", "rate": "100", "gst_percent": "18"}],
            admin(),
        )
        db.session.commit()
        purchase_id = purchase.id

    client.post(
        "/login",
        data={"email": "admin@fastockflow.local", "password": "ChangeMe123!"},
        follow_redirects=True,
    )
    response = client.get(f"/transactions/purchase/{purchase_id}/edit")
    assert response.status_code == 200
    assert b"Edit Purchase" in response.data
    assert b"UI-BILL" in response.data
