from decimal import Decimal

from app.extensions import db
from app.models import (
    FIFOConsumption,
    FIFOLayer,
    Item,
    Payable,
    Purchase,
    PurchaseLine,
    StockLedgerEntry,
    StockBook,
)
from app.services.stock import available_quantity
from app.services.transactions import (
    create_purchase,
    create_sale,
    update_purchase_header,
    update_purchase_lines,
)
from tests.test_fifo_workflows import admin, ids
from tests.test_navigation import login


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
            [
                {
                    "item_id": data["item"].id,
                    "quantity": "2",
                    "rate": "100",
                    "gst_percent": "18",
                }
            ],
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


def test_purchase_edit_can_change_total_and_status_to_paid(app):
    with app.app_context():
        data = ids()
        purchase = create_purchase(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "supplier_id": data["supplier"].id,
                "purchase_type": "GST",
                "bill_number": "STATUS-BILL",
                "bill_date": "2026-06-01",
            },
            [{"item_id": data["item"].id, "quantity": "1", "rate": "100", "gst_percent": "18"}],
            admin(),
        )
        db.session.flush()

        update_purchase_header(
            purchase,
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "purchase_type": "GST",
                "supplier_id": data["supplier"].id,
                "bill_number": "STATUS-BILL-PAID",
                "bill_date": "2026-06-02",
                "grand_total": "250",
                "payment_status": "PAID",
            },
            admin(),
        )
        db.session.commit()

        payable = Payable.query.filter_by(source_type="PURCHASE", source_id=purchase.id).one()
        assert purchase.grand_total == 250
        assert purchase.paid_amount == 250
        assert purchase.balance_amount == 0
        assert purchase.payment_status == "PAID"
        assert payable.total_amount == 250
        assert payable.paid_amount == 250
        assert payable.balance_amount == 0
        assert payable.payment_status == "PAID"


def test_purchase_edit_updates_item_quantity_rate_and_stock(app):
    with app.app_context():
        data = ids()
        purchase = create_purchase(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "supplier_id": data["supplier"].id,
                "purchase_type": "GST",
                "bill_number": "LINE-BILL",
                "bill_date": "2026-06-01",
            },
            [{"item_id": data["item"].id, "quantity": "2", "rate": "100", "gst_percent": "18"}],
            admin(),
        )
        db.session.flush()
        line = purchase.lines[0]

        update_purchase_header(
            purchase,
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "purchase_type": "GST",
                "supplier_id": data["supplier"].id,
                "bill_number": "LINE-BILL",
                "bill_date": "2026-06-01",
                "payment_status": "UNPAID",
            },
            admin(),
        )
        update_purchase_lines(
            purchase,
            [
                {
                    "line_id": line.id,
                    "item_id": data["item"].id,
                    "quantity": "3",
                    "rate": "125",
                    "gst_percent": "18",
                }
            ],
            {"payment_status": "UNPAID"},
            admin(),
        )
        db.session.commit()

        layer = FIFOLayer.query.filter_by(source_type="PURCHASE", source_id=purchase.id).one()
        ledger = StockLedgerEntry.query.filter_by(transaction_type="PURCHASE", transaction_id=purchase.id).one()
        assert purchase.grand_total == Decimal("442.50")
        assert layer.original_quantity == 3
        assert layer.available_quantity == 3
        assert layer.unit_cost == 125
        assert ledger.quantity_in == 3
        assert ledger.rate == 125
        assert available_quantity(data["ai"].id, data["ai_gst"].id, data["item"].id) == 3


def test_cash_purchase_forces_zero_gst_on_create_and_edit(app):
    with app.app_context():
        data = ids()
        cash_book = StockBook.query.filter_by(code="AI_CASH").one()
        purchase = create_purchase(
            {
                "company_id": data["ai"].id,
                "stock_book_id": cash_book.id,
                "supplier_id": data["supplier"].id,
                "purchase_type": "CASH",
                "bill_number": "CASH-GST-BILL",
                "bill_date": "2026-06-01",
            },
            [{"item_id": data["item"].id, "quantity": "2", "rate": "100", "gst_percent": "18"}],
            admin(),
        )
        db.session.flush()
        line = purchase.lines[0]

        assert purchase.subtotal == 200
        assert purchase.gst_total == 0
        assert purchase.grand_total == 200
        assert line.gst_percent == 0
        assert line.gst_amount == 0

        update_purchase_lines(
            purchase,
            [{"line_id": line.id, "item_id": data["item"].id, "quantity": "3", "rate": "125", "gst_percent": "18"}],
            {"payment_status": "UNPAID"},
            admin(),
        )
        db.session.commit()

        assert purchase.subtotal == 375
        assert purchase.gst_total == 0
        assert purchase.grand_total == 375
        assert line.gst_percent == 0
        assert line.gst_amount == 0


def test_purchase_edit_can_add_item_line_before_stock_is_consumed(app):
    with app.app_context():
        data = ids()
        replacement_item = Item.query.filter_by(code="2").one()
        purchase = create_purchase(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "supplier_id": data["supplier"].id,
                "purchase_type": "GST",
                "bill_number": "ADD-LINE-BILL",
                "bill_date": "2026-06-01",
            },
            [{"item_id": data["item"].id, "quantity": "1", "rate": "100", "gst_percent": "0"}],
            admin(),
        )
        db.session.flush()
        line = purchase.lines[0]

        update_purchase_lines(
            purchase,
            [
                {"line_id": line.id, "item_id": data["item"].id, "quantity": "1", "rate": "100", "gst_percent": "0"},
                {"item_id": replacement_item.id, "quantity": "2", "rate": "50", "gst_percent": "0"},
            ],
            {"payment_status": "UNPAID"},
            admin(),
        )
        db.session.commit()

        lines = PurchaseLine.query.filter_by(purchase_id=purchase.id).order_by(PurchaseLine.id).all()
        layers = FIFOLayer.query.filter_by(source_type="PURCHASE", source_id=purchase.id).order_by(FIFOLayer.id).all()
        assert len(lines) == 2
        assert len(layers) == 2
        assert purchase.grand_total == 200
        assert available_quantity(data["ai"].id, data["ai_gst"].id, replacement_item.id) == 2


def test_purchase_edit_can_change_item_before_stock_is_consumed(app):
    with app.app_context():
        data = ids()
        replacement_item = Item.query.filter_by(code="2").one()
        purchase = create_purchase(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "supplier_id": data["supplier"].id,
                "purchase_type": "GST",
                "bill_number": "ITEM-CHANGE-BILL",
                "bill_date": "2026-06-01",
            },
            [{"item_id": data["item"].id, "quantity": "2", "rate": "100", "gst_percent": "18"}],
            admin(),
        )
        db.session.flush()
        line = purchase.lines[0]

        update_purchase_lines(
            purchase,
            [{"line_id": line.id, "item_id": replacement_item.id, "quantity": "3", "rate": "125", "gst_percent": "18"}],
            {"payment_status": "UNPAID"},
            admin(),
        )
        db.session.commit()

        layer = FIFOLayer.query.filter_by(source_type="PURCHASE", source_id=purchase.id).one()
        ledger = StockLedgerEntry.query.filter_by(transaction_type="PURCHASE", transaction_id=purchase.id).one()
        assert line.item_id == replacement_item.id
        assert layer.item_id == replacement_item.id
        assert ledger.item_id == replacement_item.id
        assert available_quantity(data["ai"].id, data["ai_gst"].id, data["item"].id) == 0
        assert available_quantity(data["ai"].id, data["ai_gst"].id, replacement_item.id) == 3


def test_purchase_edit_updates_consumed_fifo_costs(app):
    with app.app_context():
        data = ids()
        purchase = create_purchase(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "supplier_id": data["supplier"].id,
                "purchase_type": "GST",
                "bill_number": "CONSUMED-BILL",
                "bill_date": "2026-06-01",
            },
            [{"item_id": data["item"].id, "quantity": "2", "rate": "100", "gst_percent": "18"}],
            admin(),
        )
        sale = create_sale(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "customer_id": data["customer"].id,
                "sale_type": "GST",
                "invoice_number": "CONSUME-INV",
                "invoice_date": "2026-06-02",
            },
            [
                {
                    "item_id": data["item"].id,
                    "quantity": "1",
                    "rate": "150",
                    "gst_percent": "18",
                }
            ],
            admin(),
        )
        db.session.flush()
        line = purchase.lines[0]

        update_purchase_lines(
            purchase,
            [
                {
                    "line_id": line.id,
                    "item_id": data["item"].id,
                    "quantity": "3",
                    "rate": "125",
                    "gst_percent": "18",
                }
            ],
            {"payment_status": "UNPAID"},
            admin(),
        )
        db.session.commit()

        layer = FIFOLayer.query.filter_by(source_type="PURCHASE", source_id=purchase.id).one()
        consumption = FIFOConsumption.query.filter_by(fifo_layer_id=layer.id).one()
        sale_ledger = StockLedgerEntry.query.filter_by(
            transaction_type="SALE", reference_number="CONSUME-INV"
        ).one()

        assert purchase.grand_total == Decimal("442.50")
        assert layer.original_quantity == 3
        assert layer.available_quantity == 2
        assert layer.unit_cost == 125
        assert consumption.quantity == 1
        assert consumption.rate == 125
        assert consumption.value == 125
        assert sale.fifo_cost == 125
        assert sale.gross_profit == 25
        assert sale_ledger.quantity_out == 1
        assert sale_ledger.rate == 125
        assert sale_ledger.value == 125
        assert available_quantity(data["ai"].id, data["ai_gst"].id, data["item"].id) == 2


def test_purchase_edit_can_reduce_consumed_quantity_to_negative_stock(app):
    with app.app_context():
        data = ids()
        purchase = create_purchase(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "supplier_id": data["supplier"].id,
                "purchase_type": "GST",
                "bill_number": "CONSUMED-REDUCE-BILL",
                "bill_date": "2026-06-01",
            },
            [
                {
                    "item_id": data["item"].id,
                    "quantity": "2",
                    "rate": "100",
                    "gst_percent": "0",
                }
            ],
            admin(),
        )
        sale = create_sale(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "customer_id": data["customer"].id,
                "sale_type": "GST",
                "invoice_number": "CONSUME-REDUCE-INV",
                "invoice_date": "2026-06-02",
            },
            [
                {
                    "item_id": data["item"].id,
                    "quantity": "2",
                    "rate": "150",
                    "gst_percent": "0",
                }
            ],
            admin(),
        )
        db.session.flush()
        line = purchase.lines[0]

        update_purchase_lines(
            purchase,
            [
                {
                    "line_id": line.id,
                    "item_id": data["item"].id,
                    "quantity": "1",
                    "rate": "100",
                    "gst_percent": "0",
                }
            ],
            {"payment_status": "UNPAID"},
            admin(),
        )
        db.session.commit()

        layer = FIFOLayer.query.filter_by(source_type="PURCHASE", source_id=purchase.id).one()
        consumption = FIFOConsumption.query.filter_by(fifo_layer_id=layer.id).one()
        sale_ledgers = StockLedgerEntry.query.filter_by(
            transaction_type="SALE", reference_number="CONSUME-REDUCE-INV"
        ).order_by(StockLedgerEntry.rate.desc()).all()

        assert purchase.grand_total == 100
        assert layer.original_quantity == 1
        assert layer.available_quantity == 0
        assert consumption.quantity == 1
        assert consumption.value == 100
        assert sale.fifo_cost == 100
        assert sale.gross_profit == 200
        assert [ledger.quantity_out for ledger in sale_ledgers] == [
            Decimal("1.000"),
            Decimal("1.000"),
        ]
        assert [ledger.value for ledger in sale_ledgers] == [Decimal("100.00"), Decimal("0.00")]
        assert available_quantity(data["ai"].id, data["ai_gst"].id, data["item"].id) == -1


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

    login(client)
    response = client.get(f"/transactions/purchase/{purchase_id}/edit")
    assert response.status_code == 200
    assert b"Edit Purchase" in response.data
    assert b"UI-BILL" in response.data
    assert b"data-item-search" in response.data
    assert b"data-item-value" in response.data
    assert b"data-document-total-preview" in response.data


def test_company_user_sees_edit_for_existing_purchase(client, app):
    with app.app_context():
        data = ids()
        purchase = create_purchase(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "supplier_id": data["supplier"].id,
                "purchase_type": "GST",
                "bill_number": "STOCK-EDIT-BILL",
                "bill_date": "2026-06-01",
            },
            [{"item_id": data["item"].id, "quantity": "1", "rate": "100", "gst_percent": "18"}],
            admin(),
        )
        db.session.commit()
        edit_href = f"/transactions/purchase/{purchase.id}/edit"

    login(client)
    list_response = client.get("/transactions/purchase")
    assert list_response.status_code == 200
    assert edit_href.encode() in list_response.data

    edit_response = client.get(edit_href)
    assert edit_response.status_code == 200
    assert b"STOCK-EDIT-BILL" in edit_response.data
