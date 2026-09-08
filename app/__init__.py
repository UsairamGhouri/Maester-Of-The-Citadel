import os
import logging
from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

from app.config import Config

# Initialize extensions (bound to app in factory)
db = SQLAlchemy()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger('CourseHelper')


def create_app(config_class=Config):
    """Flask application factory."""
    app = Flask(
        __name__,
        static_folder='static',
        template_folder='templates',
    )
    app.config.from_object(config_class)

    # ── Initialize Extensions ──────────────────────────────────────────
    CORS(app)
    db.init_app(app)

    # ── Ensure Required Directories Exist ──────────────────────────────
    dirs_to_create = [
        config_class.DATA_DIR,
        config_class.UPLOAD_DIR,
        config_class.CHROMA_PERSIST_DIR,
    ]
    for dir_path in dirs_to_create:
        os.makedirs(dir_path, exist_ok=True)

    # ── Register Blueprints ────────────────────────────────────────────
    from app.routes.pages import pages_bp
    from app.routes.upload import upload_bp
    from app.routes.books import books_bp
    from app.routes.chat import chat_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(books_bp)
    app.register_blueprint(chat_bp)

    # ── Create Database Tables ─────────────────────────────────────────
    with app.app_context():
        # Import models so SQLAlchemy knows about them
        from app.models import database  # noqa: F401
        db.create_all()
        logger.info('Database tables initialized.')

    logger.info(f'Course Helper app created. DB: {config_class.DB_PATH}')
    return app
