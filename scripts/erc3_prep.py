#!/usr/bin/env python
"""
ERC3 benchmark preparation CLI.

Provides easy access to wiki ingestion, specs export, and rule extraction.
Wikis are stored by SHA prefix only - shared across benchmarks.

Usage:
    python scripts/erc3_prep.py ingest erc3-dev       # Download wikis for benchmark
    python scripts/erc3_prep.py export erc3-dev       # Export specs to docs
    python scripts/erc3_prep.py tag-files             # Tag all wiki files
    python scripts/erc3_prep.py extract-rules         # Extract rules from all wikis
    python scripts/erc3_prep.py all erc3-dev          # All: ingest + export
    python scripts/erc3_prep.py all                   # All benchmarks
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.erc3.wiki import ingest_wikis, export_specs_info, get_wiki_data_path, tag_wiki_files
from benchmarks.erc3.rules import extract_all_rules


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


def cmd_extract_rules(args):
    """Extract rules from wiki files (all wikis, shared across benchmarks)."""
    print(f"\n{'='*60}")
    print(f"Extracting rules from all wikis")
    print('='*60)
    
    # Get wiki data directory (shared across all benchmarks)
    wiki_base = get_wiki_data_path()
    
    if not wiki_base.exists():
        print("  No wiki data found. Run 'ingest' first.")
        return
    
    # Iterate over all SHA1 directories
    for sha_dir in wiki_base.iterdir():
        if not sha_dir.is_dir():
            continue
        
        manifest_path = sha_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        
        rules_dir = sha_dir / "rules"
        if rules_dir.exists() and not args.force:
            print(f"  {sha_dir.name}: rules/ already exists, skipping (use --force to overwrite)")
            continue
        
        print(f"\n  {sha_dir.name}:")
        try:
            extract_all_rules(str(sha_dir))
        except Exception as e:
            print(f"  ✗ Error: {e}")


def cmd_tag_files(args):
    """Tag wiki files with has_rules flag (all wikis, shared across benchmarks)."""
    import json
    
    print(f"\n{'='*60}")
    print(f"Tagging files for all wikis")
    print('='*60)
    
    wiki_base = get_wiki_data_path()
    
    if not wiki_base.exists():
        print("  No wiki data found. Run 'ingest' first.")
        return
    
    for sha_dir in wiki_base.iterdir():
        if not sha_dir.is_dir():
            continue
        
        manifest_path = sha_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        
        # Check if already tagged
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        already_tagged = any("has_rules" in f for f in manifest.get("files", []))
        if already_tagged and not args.force:
            print(f"  {sha_dir.name}: already tagged, skipping (use --force to re-tag)")
            continue
        
        print(f"\n  {sha_dir.name}:")
        try:
            result = tag_wiki_files(str(sha_dir))
            print(f"  Tagged {result['tagged']} files, {result['with_rules']} have rules")
        except Exception as e:
            print(f"  ✗ Error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="ERC3 benchmark preparation tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/erc3_prep.py ingest erc3-dev       Download wikis for erc3-dev
  python scripts/erc3_prep.py tag-files             Tag all wiki files with has_rules
  python scripts/erc3_prep.py extract-rules         Extract rules from all wikis
  python scripts/erc3_prep.py export erc3-test      Export specs for erc3-test
  python scripts/erc3_prep.py all erc3-dev          Both ingest + export for erc3-dev
  python scripts/erc3_prep.py all                   All benchmarks (erc3-dev, erc3-test, erc3)
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
    
    # Tag files command (works on all wikis - shared across benchmarks)
    tag_parser = subparsers.add_parser("tag-files", help="Tag files with has_rules flag (all wikis)")
    tag_parser.add_argument(
        "--force", "-f", action="store_true",
        help="Re-tag even if already tagged"
    )
    tag_parser.set_defaults(func=cmd_tag_files)
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export specs info to markdown")
    export_parser.add_argument(
        "benchmarks", nargs="*",
        help="Benchmark names (default: all erc3 variants)"
    )
    export_parser.set_defaults(func=cmd_export)
    
    # Extract rules command (works on all wikis - shared across benchmarks)
    extract_parser = subparsers.add_parser("extract-rules", help="Extract rules from wiki files (all wikis)")
    extract_parser.add_argument(
        "--force", "-f", action="store_true",
        help="Overwrite existing rules/ folder"
    )
    extract_parser.set_defaults(func=cmd_extract_rules)
    
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

