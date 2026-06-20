from app.extensions import db
from app.models import (
    FIFOLayer,
    Payable,
    Receivable,
    Sale,
    StockLedgerEntry,
    User,
)
from app.services.transactions import (
    create_opening_stock,
    create_sale,
    create_transfer,
    update_sale_header,
    update_transfer_header,
)
from tests.test_fifo_workflows import admin, ids


def seed_stock(data, reference="EDIT-STOCK"):
    create_opening_stock(
        {
            "company_id": data["ai"].id,
            "stock_book_id": data["ai_gst"].id,
            "reference_number": reference,
            "opening_date": "2026-06-01",
        },
        [{"item_id": data["item"].id, "quantity": "10", "rate": "100"}],
        admin(),
    )


def test_sale_header_edit_updates_receivable_and_ledger(app):
    with app.app_context():
        data = ids()
        seed_stock(data)
        sale = create_sale(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "customer_id": data["customer"].id,
                "sale_type": "GST",
                "invoice_number": "OLD-INV",
                "invoice_date": "2026-06-02",
                "due_date": "2026-06-20",
            },
            [{"item_id": data["item"].id, "quantity": "1", "rate": "150", "gst_percent": "18"}],
            admin(),
        )
        db.session.flush()

        update_sale_header(
            sale,
            {
                "customer_id": data["customer"].id,
                "invoice_number": "NEW-INV",
                "invoice_date": "2026-06-03",
                "due_date": "2026-06-25",
                "remarks": "Corrected invoice details",
            },
            admin(),
        )
        db.session.commit()

        sale = Sale.query.filter_by(invoice_number="NEW-INV").one()
        receivable = Receivable.query.filter_by(source_type="SALE", source_id=sale.id).one()
        ledger = StockLedgerEntry.query.filter_by(
            transaction_type="SALE", transaction_id=sale.id
        ).one()

        assert sale.remarks == "Corrected invoice details"
        assert receivable.document_number == "NEW-INV"
        assert str(receivable.due_date) == "2026-06-25"
        assert ledger.reference_number == "NEW-INV"
        assert str(ledger.entry_date) == "2026-06-03"


def test_sales_user_sees_edit_for_existing_sale(client, app):
    with app.app_context():
        sales_user = User(
            name="Sales User",
            email="sales@example.com",
            role="SALES",
            active=True,
        )
        sales_user.set_password("Sales123!")
        db.session.add(sales_user)
        data = ids()
        seed_stock(data, "SALES-UI-STOCK")
        sale = create_sale(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "customer_id": data["customer"].id,
                "sale_type": "GST",
                "invoice_number": "SALES-EDIT-INV",
                "invoice_date": "2026-06-02",
            },
            [{"item_id": data["item"].id, "quantity": "1", "rate": "150", "gst_percent": "18"}],
            admin(),
        )
        db.session.commit()
        edit_href = f"/transactions/sale/{sale.id}/edit"

    client.post(
        "/login",
        data={"email": "sales@example.com", "password": "Sales123!"},
        follow_redirects=True,
    )
    list_response = client.get("/transactions/sale")
    assert list_response.status_code == 200
    assert edit_href.encode() in list_response.data

    edit_response = client.get(edit_href)
    assert edit_response.status_code == 200
    assert b"SALES-EDIT-INV" in edit_response.data


def test_transfer_header_edit_updates_linked_references(app):
    with app.app_context():
        data = ids()
        seed_stock(data, "TRF-EDIT-STOCK")
        transfer = create_transfer(
            {
                "from_company_id": data["ai"].id,
                "from_stock_book_id": data["ai_gst"].id,
                "to_company_id": data["fml"].id,
                "to_stock_book_id": data["fml_gst"].id,
                "reference_number": "OLD-TRF",
                "transfer_date": "2026-06-02",
            },
            [{"item_id": data["item"].id, "quantity": "2"}],
            admin(),
        )
        db.session.flush()

        update_transfer_header(
            transfer,
            {
                "reference_number": "NEW-TRF",
                "transfer_date": "2026-06-03",
                "reason": "Corrected order reference",
                "remarks": "Corrected transfer details",
            },
            admin(),
        )
        db.session.commit()

        layer = FIFOLayer.query.filter_by(source_type="TRANSFER_IN", source_id=transfer.id).one()
        ledger_entries = StockLedgerEntry.query.filter_by(
            transaction_type="TRANSFER", transaction_id=transfer.id
        ).all()
        payable = Payable.query.filter_by(source_type="INTER_COMPANY", source_id=transfer.id).one()
        receivable = Receivable.query.filter_by(source_type="INTER_COMPANY", source_id=transfer.id).one()

        assert transfer.reference_number == "NEW-TRF"
        assert transfer.reason == "Corrected order reference"
        assert layer.source_reference == "NEW-TRF"
        assert str(layer.source_date) == "2026-06-03"
        assert {entry.reference_number for entry in ledger_entries} == {"NEW-TRF"}
        assert payable.document_number == "NEW-TRF"
        assert receivable.document_number == "NEW-TRF"


def test_stock_user_sees_edit_for_existing_transfer(client, app):
    with app.app_context():
        stock_user = User(
            name="Transfer Stock User",
            email="transfer-stock@example.com",
            role="STOCK",
            active=True,
        )
        stock_user.set_password("Stock123!")
        db.session.add(stock_user)
        data = ids()
        seed_stock(data, "TRF-UI-STOCK")
        transfer = create_transfer(
            {
                "from_company_id": data["ai"].id,
                "from_stock_book_id": data["ai_gst"].id,
                "to_company_id": data["fml"].id,
                "to_stock_book_id": data["fml_gst"].id,
                "reference_number": "STOCK-EDIT-TRF",
                "transfer_date": "2026-06-02",
            },
            [{"item_id": data["item"].id, "quantity": "1"}],
            admin(),
        )
        db.session.commit()
        edit_href = f"/transactions/transfer/{transfer.id}/edit"

    client.post(
        "/login",
        data={"email": "transfer-stock@example.com", "password": "Stock123!"},
        follow_redirects=True,
    )
    list_response = client.get("/transactions/transfer")
    assert list_response.status_code == 200
    assert edit_href.encode() in list_response.data

    edit_response = client.get(edit_href)
    assert edit_response.status_code == 200
    assert b"STOCK-EDIT-TRF" in edit_response.data
