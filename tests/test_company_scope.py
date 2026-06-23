from app.models import Purchase
from app.services.transactions import create_purchase
from tests.test_fifo_workflows import admin, ids
from tests.test_navigation import login
from app.extensions import db


def test_fixed_company_purchase_form_only_offers_active_company(client):
    login(client, "firsttech.user", "Firsttech2026")

    response = client.get("/transactions/purchase")

    assert response.status_code == 200
    assert b"FML - FirstTech Machine LLP" in response.data
    assert b"AI - Aditya International" not in response.data


def test_fixed_company_user_cannot_submit_other_company_purchase(client, app):
    with app.app_context():
        data = ids()
        payload = {
            "company_id": data["ai"].id,
            "stock_book_id": data["ai_gst"].id,
            "supplier_id": data["supplier"].id,
            "purchase_type": "GST",
            "bill_number": "CROSS-COMPANY-BILL",
            "bill_date": "2026-06-22",
            "item_id[]": [data["item"].id],
            "quantity[]": ["1"],
            "rate[]": ["100"],
            "gst_percent[]": ["18"],
        }

    login(client, "firsttech.user", "Firsttech2026")
    response = client.post("/transactions/purchase", data=payload, follow_redirects=True)

    assert response.status_code == 200
    assert b"active company" in response.data
    with app.app_context():
        assert Purchase.query.filter_by(bill_number="CROSS-COMPANY-BILL").count() == 0


def test_reports_are_scoped_to_active_company(client, app):
    with app.app_context():
        data = ids()
        create_purchase(
            {
                "company_id": data["fml"].id,
                "stock_book_id": data["fml_gst"].id,
                "supplier_id": data["supplier"].id,
                "purchase_type": "GST",
                "bill_number": "FML-SCOPED-BILL",
                "bill_date": "2026-06-22",
            },
            [{"item_id": data["item"].id, "quantity": "1", "rate": "100", "gst_percent": "18"}],
            admin(),
        )
        create_purchase(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "supplier_id": data["supplier"].id,
                "purchase_type": "GST",
                "bill_number": "AI-HIDDEN-BILL",
                "bill_date": "2026-06-22",
            },
            [{"item_id": data["item"].id, "quantity": "1", "rate": "100", "gst_percent": "18"}],
            admin(),
        )
        db.session.commit()

    login(client, "firsttech.user", "Firsttech2026")
    response = client.get("/reports/purchases")

    assert response.status_code == 200
    assert b"FML-SCOPED-BILL" in response.data
    assert b"AI-HIDDEN-BILL" not in response.data
