from app.extensions import db
from app.services.transactions import create_purchase
from tests.test_fifo_workflows import admin, ids
from tests.test_navigation import login


def test_duplicate_customer_code_shows_friendly_error(client, app):
    with app.app_context():
        customer_code = ids()["customer"].code

    login(client)
    response = client.post(
        "/masters/customers/new",
        data={
            "code": customer_code,
            "name": "Duplicate Customer",
            "customer_type": "CASH_AND_BILL",
            "default_credit_days": "30",
            "active": "on",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"already exists" in response.data
    assert b"IntegrityError" not in response.data
    assert b"Duplicate entry" not in response.data


def test_master_lists_include_live_search_and_find_button(client):
    login(client)

    response = client.get("/masters/items")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "data-live-search" in html
    assert "data-live-target" in html
    assert "<datalist" in html
    assert ">Find</button>" in html


def test_supplier_master_has_transactions_drilldown(client, app):
    with app.app_context():
        data = ids()
        create_purchase(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "supplier_id": data["supplier"].id,
                "purchase_type": "GST",
                "bill_number": "SUP-MASTER-TXN",
                "bill_date": "2026-06-25",
            },
            [{"item_id": data["item"].id, "quantity": "1", "rate": "100", "gst_percent": "18"}],
            admin(),
        )
        supplier_id = data["supplier"].id
        db.session.commit()

    login(client)
    response = client.get("/masters/suppliers")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert f"/masters/suppliers/{supplier_id}/transactions" in html
    assert "Transactions" in html


def test_customer_form_has_cash_bill_and_combined_type_options(client):
    login(client)

    response = client.get("/masters/customers/new")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'value="CASH"' in html
    assert 'value="BILL"' in html
    assert 'value="CASH_AND_BILL"' in html
