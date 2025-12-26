"""
ERC3 ingestion module.

One-time preparation operations: wiki download, indexing, rule extraction, specs export.

Usage:
    from benchmarks.erc3.ingestion import ingest_wikis, index_wiki_files, extract_all_rules, export_specs_info
"""

from .wiki import ingest_wikis, index_wiki_files, get_wiki_data_path
from .rules import extract_all_rules
from .specs import export_specs_info

__all__ = [
    "ingest_wikis",
    "index_wiki_files", 
    "get_wiki_data_path",
    "extract_all_rules",
    "export_specs_info",
]

