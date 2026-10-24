"""Vercel serverless entrypoint for the FastAPI app.

Vercel's Python runtime serves files under api/ as serverless functions.
This module re-exports the FastAPI application defined in main.py so the
whole app (API + static frontend) runs behind a single function.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402,F401

__all__ = ["app"]
