#!/usr/bin/env python3
"""
Hermeneia web server.

Usage:
    python scripts/herm_server.py [--db build/hermeneia.db] [--port 5173]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from hermeneia.web.app import create_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hermeneia web server")
    parser.add_argument("--db", default="build/hermeneia.db")
    parser.add_argument("--port", type=int, default=5173)
    args = parser.parse_args()

    app = create_app(db_path=args.db)
    print(f"  Hermeneia → http://localhost:{args.port}")
    print(f"  Database  → {args.db}")
    app.run(port=args.port, debug=False)
