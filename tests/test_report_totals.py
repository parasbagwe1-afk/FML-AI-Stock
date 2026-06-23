from app.extensions import db
from app.services.transactions import create_sale
from tests.test_fifo_workflows import admin, ids
from tests.test_navigation import login


def test_sales_report_displays_money_totals(client, app):
    with app.app_context():
        data = ids()
        create_sale(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "customer_id": data["customer"].id,
                "sale_type": "GST",
                "invoice_number": "REPORT-TOTAL-INV",
                "invoice_date": "2026-06-23",
            },
            [{"item_id": data["item"].id, "quantity": "1", "rate": "100", "gst_percent": "18"}],
            admin(),
        )
        db.session.commit()

    login(client)
    response = client.get("/reports/sales")

    assert response.status_code == 200
    assert b"Shown rows total" in response.data
    assert b"Grand total" in response.data
    assert "₹118.00".encode() in response.data


def test_outstanding_customer_search_shows_filtered_balance_summary(client, app):
    with app.app_context():
        data = ids()
        create_sale(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "customer_id": data["customer"].id,
                "sale_type": "GST",
                "invoice_number": "CUSTOMER-OUTSTANDING-INV",
                "invoice_date": "2026-06-23",
            },
            [{"item_id": data["item"].id, "quantity": "1", "rate": "250", "gst_percent": "18"}],
            admin(),
        )
        customer_name = data["customer"].name
        db.session.commit()

    login(client)
    response = client.get(f"/finance/outstanding?q={customer_name}")

    assert response.status_code == 200
    assert b"Customer Balance" in response.data
    assert "₹295.00".encode() in response.data
    assert b"CUSTOMER-OUTSTANDING-INV" in response.data
