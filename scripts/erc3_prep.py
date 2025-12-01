#!/usr/bin/env python
"""
ERC3 benchmark preparation CLI.

Provides easy access to wiki ingestion and specs export.

Usage:
    python scripts/erc3_prep.py ingest erc3-dev     # Download wikis
    python scripts/erc3_prep.py export erc3-dev    # Export specs to docs
    python scripts/erc3_prep.py all erc3-dev       # Both ingest + export
    python scripts/erc3_prep.py all                # All benchmarks
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.erc3.wiki import ingest_wikis, export_specs_info


# Known ERC3 benchmark variants
ERC3_BENCHMARKS = ["erc3-dev", "erc3-test", "erc3"]


def cmd_ingest(args):
    """Download and cache wiki files."""
    benchmarks = args.benchmarks if args.benchmarks else ERC3_BENCHMARKS
    
    for benchmark in benchmarks:
        print(f"\n{'='*60}")
        print(f"Ingesting wikis for: {benchmark}")
        print('='*60)
        try:
            ingest_wikis(benchmark)
        except Exception as e:
            print(f"✗ Error: {e}")


def cmd_export(args):
    """Export specs info to markdown."""
    benchmarks = args.benchmarks if args.benchmarks else ERC3_BENCHMARKS
    
    for benchmark in benchmarks:
        print(f"\nExporting specs for: {benchmark}")
        try:
            export_specs_info(benchmark)
        except Exception as e:
            print(f"✗ Error: {e}")


def cmd_all(args):
    """Run both ingest and export."""
    cmd_ingest(args)
    print("\n" + "="*60)
    cmd_export(args)


def main():
    parser = argparse.ArgumentParser(
        description="ERC3 benchmark preparation tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/erc3_prep.py ingest erc3-dev     Download wikis for erc3-dev
  python scripts/erc3_prep.py export erc3-test    Export specs for erc3-test
  python scripts/erc3_prep.py all erc3-dev        Both for erc3-dev
  python scripts/erc3_prep.py all                 All benchmarks (erc3-dev, erc3-test, erc3)
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Download and cache wiki files")
    ingest_parser.add_argument(
        "benchmarks", nargs="*", 
        help="Benchmark names (default: all erc3 variants)"
    )
    ingest_parser.set_defaults(func=cmd_ingest)
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export specs info to markdown")
    export_parser.add_argument(
        "benchmarks", nargs="*",
        help="Benchmark names (default: all erc3 variants)"
    )
    export_parser.set_defaults(func=cmd_export)
    
    # All command
    all_parser = subparsers.add_parser("all", help="Run both ingest and export")
    all_parser.add_argument(
        "benchmarks", nargs="*",
        help="Benchmark names (default: all erc3 variants)"
    )
    all_parser.set_defaults(func=cmd_all)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()

