from app.core.company_context import ACTIVE_COMPANY_SESSION_KEY
from app.models import Company


def choose_company(client, code="AI"):
    with client.application.app_context():
        company = Company.query.filter_by(code=code).one()
        company_id = company.id
    with client.session_transaction() as session:
        session[ACTIVE_COMPANY_SESSION_KEY] = company_id


def login(client, login_id="adityainternational.user", password="Aditya2026", company_code=None):
    response = client.post(
        "/login",
        data={"email": login_id, "password": password},
        follow_redirects=True,
    )
    if company_code:
        choose_company(client, company_code)
    return response


def test_company_login_selects_aditya_context(client):
    response = login(client)
    assert response.status_code == 200
    assert b"Aditya International" in response.data
    assert b"Choose Company" not in response.data


def test_company_login_selects_firsttech_context(client):
    response = login(client, "firsttech.user", "Firsttech2026")
    assert response.status_code == 200
    assert b"FirstTech Machine LLP" in response.data
    assert b"Choose Company" not in response.data


def test_fixed_company_login_cannot_switch_company(client):
    login(client, "firsttech.user", "Firsttech2026")
    with client.application.app_context():
        aditya = Company.query.filter_by(code="AI").one()
    response = client.post(
        "/company/select",
        data={"company_id": aditya.id, "next": "/dashboard/"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"FirstTech Machine LLP" in response.data
    assert b"Aditya International</button>" not in response.data


def test_admin_login_uses_company_chooser(client):
    response = login(client, "admin@fastockflow.local", "ChangeMe123!")
    assert response.status_code == 200
    assert b"Choose Company" in response.data
    assert b"FirstTech Machine LLP" in response.data
    assert b"Aditya International" in response.data


def test_master_sidebar_marks_only_current_menu_active(client):
    login(client)
    response = client.get("/masters/items")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    nav_html = html.split('<nav class="nav">', 1)[1].split("</nav>", 1)[0]
    assert nav_html.count('class="active"') == 1
    assert 'class="active">Items</a>' in nav_html
    assert 'class="active">Customers</a>' not in nav_html
    assert 'class="active">Suppliers</a>' not in nav_html


def test_sidebar_company_names_switch_company_context(client):
    login(client)
    response = client.get("/transactions/opening")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'action="/company/select"' in html
    assert 'Aditya International</button>' in html
    assert 'FirstTech Machine LLP</button>' not in html


def test_topbar_includes_music_controls(client):
    login(client)
    response = client.get("/dashboard/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-music-toggle' in html
    assert 'data-music-volume' in html
    assert 'aria-label="Background music volume"' in html
