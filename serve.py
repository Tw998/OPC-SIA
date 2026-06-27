#!/usr/bin/env python3
"""Hitpoint Sales Intelligence — WSGI entrypoint & local dev launcher.

Vercel imports this file and reads the `app` variable.
Local dev: python3 serve.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import app  # noqa: F401 — Vercel reads this; import also bootstraps the DB

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    print(f"\n🌐 Hitpoint Sales Intelligence")
    print(f"   http://localhost:{port}\n", flush=True)
    app.run(debug=False, host="0.0.0.0", port=port, use_reloader=False)
