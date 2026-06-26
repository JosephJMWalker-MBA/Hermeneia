#!/usr/bin/env python3
"""
Hermeneia Compiler Pipeline — entry point.

Usage:
    python scripts/run_pipeline.py --pdf examples/gatsby.pdf

Output:
    build/
        hermeneia.db
        gatsby.herm/
            context.json
            hermeneia.db
"""
import argparse
import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from hermeneia.compiler.compiler import Compiler


def main() -> None:
    parser = argparse.ArgumentParser(description="Hermeneia compiler pipeline")
    parser.add_argument("--pdf", required=True, help="Path to source PDF")
    parser.add_argument("--build", default="build", help="Build output directory")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    build_dir = Path(args.build)
    build_dir.mkdir(parents=True, exist_ok=True)
    db_path = build_dir / "hermeneia.db"

    compiler = Compiler(db_path=db_path, build_dir=build_dir)
    try:
        bundle_dir = compiler.compile(pdf_path)
        print(f"\nSuccess.")
        print(f"  Database : {db_path}")
        print(f"  Bundle   : {bundle_dir}")
        for f in sorted(bundle_dir.iterdir()):
            size = f.stat().st_size
            print(f"    {f.name:30s}  {size:>10,} bytes")
    finally:
        compiler.close()


if __name__ == "__main__":
    main()
