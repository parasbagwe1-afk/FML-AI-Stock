from app.extensions import db
from app.models import Customer
from app.services.transactions import create_purchase, create_sale
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


def test_duplicate_customer_name_is_blocked_case_insensitively(client, app):
    with app.app_context():
        existing_name = ids()["customer"].name

    login(client)
    response = client.post(
        "/masters/customers/new",
        data={
            "code": "UNIQUECASE01",
            "name": existing_name.upper(),
            "customer_type": "CASH_AND_BILL",
            "default_credit_days": "30",
            "active": "on",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"already exists" in response.data
    assert b"Open the existing customer" in response.data


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


def test_unused_customer_can_be_deleted_from_directory(client, app):
    with app.app_context():
        customer = Customer(
            code="DEL001",
            name="Delete Me Customer",
            customer_type="CASH_AND_BILL",
            default_credit_days=30,
            active=True,
        )
        db.session.add(customer)
        db.session.commit()
        customer_id = customer.id

    login(client)
    response = client.post(f"/masters/customers/{customer_id}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"Customer deleted" in response.data
    with app.app_context():
        assert db.session.get(Customer, customer_id) is None


def test_customer_with_transactions_is_deactivated_instead_of_deleted(client, app):
    with app.app_context():
        data = ids()
        customer = Customer(
            code="DELTXN001",
            name="Delete Transaction Customer",
            customer_type="CASH_AND_BILL",
            default_credit_days=30,
            active=True,
        )
        db.session.add(customer)
        db.session.flush()
        create_sale(
            {
                "company_id": data["ai"].id,
                "stock_book_id": data["ai_gst"].id,
                "customer_id": customer.id,
                "sale_type": "GST",
                "invoice_number": "DELTXN-INV-1",
                "invoice_date": "2026-06-25",
            },
            [{"item_id": data["item"].id, "quantity": "1", "rate": "100", "gst_percent": "18"}],
            admin(),
        )
        db.session.commit()
        customer_id = customer.id

    login(client)
    response = client.post(f"/masters/customers/{customer_id}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert b"deactivated instead of permanently deleted" in response.data
    with app.app_context():
        customer = db.session.get(Customer, customer_id)
        assert customer is not None
        assert customer.active is False


def test_customer_form_has_cash_bill_and_combined_type_options(client):
    login(client)

    response = client.get("/masters/customers/new")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'value="CASH"' in html
    assert 'value="BILL"' in html
    assert 'value="CASH_AND_BILL"' in html
