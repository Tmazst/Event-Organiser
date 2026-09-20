from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
import hmac
import secrets
import shutil

import click
from flask import Flask, abort, render_template, request, send_from_directory, session
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from .extensions import db, login_manager, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    if not app.config.get("TESTING") and app.config["SECRET_KEY"] == "dev-change-me":
        raise RuntimeError("Set a strong SECRET_KEY before starting Event Organiser.")

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    css_path = Path(app.static_folder) / "css" / "app.css"
    app.config["APP_CSS_VERSION"] = str(int(css_path.stat().st_mtime)) if css_path.exists() else "1"

    @app.template_filter("moneyfmt")
    def moneyfmt(value, places=2):
        return f"{Decimal(value or 0):,.{places}f}"

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    @app.cli.command("migrate-event-photos")
    def migrate_event_photos():
        """Move legacy public event photos into authenticated storage."""
        legacy_photos = Path(app.config["LEGACY_EVENT_PHOTO_FOLDER"])
        private_photos = Path(app.config["EVENT_PHOTO_FOLDER"])
        moved = 0
        if legacy_photos.exists():
            for old_file in legacy_photos.rglob("*"):
                if not old_file.is_file() or old_file.name == ".gitkeep":
                    continue
                destination = private_photos / old_file.relative_to(legacy_photos)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    old_file.unlink()
                else:
                    shutil.move(str(old_file), str(destination))
                moved += 1
        click.echo(f"Migrated {moved} event photo{'s' if moved != 1 else ''}.")

    @app.get("/manifest.webmanifest")
    def web_manifest():
        return send_from_directory(
            app.static_folder, "manifest.webmanifest",
            mimetype="application/manifest+json",
        )

    @app.get("/service-worker.js")
    def service_worker():
        response = send_from_directory(
            app.static_folder, "service-worker.js",
            mimetype="application/javascript",
        )
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    @app.context_processor
    def csrf_helpers():
        def csrf_token():
            token = session.get("csrf_token")
            if token is None:
                token = secrets.token_urlsafe(32)
                session["csrf_token"] = token
            return token
        return {
            "csrf_token": csrf_token,
            "current_year": datetime.now(timezone.utc).year,
            "app_css_version": app.config["APP_CSS_VERSION"],
        }

    @app.before_request
    def csrf_protect():
        if not app.config.get("CSRF_PROTECT", True) or request.method != "POST":
            return None
        if request.endpoint == "mojapos_payments.mojapos_callback":
            return None
        expected = session.get("csrf_token", "")
        supplied = request.form.get("csrf_token", "")
        if not expected or not hmac.compare_digest(expected, supplied):
            abort(400, description="Invalid or missing form token.")
        return None

    @app.errorhandler(400)
    def bad_request(error):
        if error.description == "Invalid or missing form token.":
            return render_template("csrf_expired.html"), 400
        return error

    @app.after_request
    def apply_browser_security(response):
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:; "
            "img-src 'self' data:; connect-src 'self' https:; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .routes import bp
    app.register_blueprint(bp)

    from .billing import bp as billing_bp
    app.register_blueprint(billing_bp)

    from .payment_gateway import build_gateway
    build_gateway().init_app(app)

    return app
