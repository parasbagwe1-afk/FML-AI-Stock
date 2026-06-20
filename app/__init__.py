from datetime import date, timedelta
from pathlib import Path

from flask import Flask, render_template, request
from flask_login import current_user

from app.config import Config
from app.extensions import csrf, db, login_manager


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or Config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app import models  # noqa: F401
    from app.auth.routes import bp as auth_bp
    from app.dashboard.routes import bp as dashboard_bp
    from app.masters.routes import bp as masters_bp
    from app.payments.routes import bp as payments_bp
    from app.reports.routes import bp as reports_bp
    from app.transactions.routes import bp as transactions_bp
    from app.users.routes import bp as users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(masters_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(users_bp)

    register_template_helpers(app)
    register_cli(app)
    register_error_handlers(app)
    return app


def register_template_helpers(app):
    from app.core.formatting import fmt_money, fmt_qty
    from app.core.security import can
    from app.models import Payable, Receivable

    @app.context_processor
    def inject_helpers():
        def is_active_nav(endpoint, params=None):
            if request.endpoint != endpoint:
                return False
            params = params or {}
            for key, expected in params.items():
                if (request.view_args or {}).get(key) != expected:
                    return False
            return True

        def due_alert_count():
            if not current_user.is_authenticated or not can(current_user, "due_alerts", "view"):
                return None
            today = date.today()
            upcoming = today + timedelta(days=7)
            receivables = Receivable.query.filter(
                Receivable.balance_amount > 0,
                Receivable.due_date <= upcoming,
            ).count()
            payables = Payable.query.filter(
                Payable.balance_amount > 0,
                Payable.due_date <= upcoming,
            ).count()
            return receivables + payables

        return {
            "can": can,
            "fmt_money": fmt_money,
            "fmt_qty": fmt_qty,
            "is_active_nav": is_active_nav,
            "due_alert_count": due_alert_count(),
            "asset_version": app.config.get("STATIC_ASSET_VERSION", "1"),
        }


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create database tables."""
        db.create_all()
        print("Database tables created.")

    @app.cli.command("drop-db")
    def drop_db():
        """Drop database tables. Development only."""
        db.drop_all()
        print("Database tables dropped.")

    @app.cli.command("seed-data")
    def seed_data_command():
        """Seed default companies, stock books, masters, payment modes, and admin."""
        from app.services.seed import seed_all

        seed_all(app)
        print("Seed data ready.")


def register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500
