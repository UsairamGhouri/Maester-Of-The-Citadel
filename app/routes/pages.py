"""Serves the main single-page application."""
from flask import Blueprint, render_template

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def index():
    """Render the main application shell."""
    return render_template('index.html')
