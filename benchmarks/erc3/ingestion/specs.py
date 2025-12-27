"""
Benchmark specs export for ERC3.

Exports benchmark metadata to markdown files for development reference.

Usage:
    from benchmarks.erc3.ingestion import export_specs_info
    
    export_specs_info("erc3-dev")  # Creates docs/erc3/erc3-dev_specs.md
"""

from pathlib import Path

from erc3 import ERC3
import config

# Path to docs directory (project root)
DOCS_DIR = Path(__file__).parent.parent.parent.parent / "docs" / "erc3"


def export_specs_info(benchmark_name: str) -> Path:
    """
    Export benchmark specs info to a markdown file for development reference.
    
    Creates a human-readable markdown file with all task specs, including:
    - Task index and ID
    - Task description
    - Gotcha/hints (if any)
    - Available API routes
    
    Args:
        benchmark_name: Name of the benchmark (e.g., "erc3-dev", "erc3-test", "erc3")
    
    Returns:
        Path to the created markdown file
    """
    # Validate benchmark name
    if not benchmark_name.startswith("erc3"):
        raise ValueError(f"Specs export only supports erc3* benchmarks, got: {benchmark_name}")
    
    # Initialize ERC3 client and get benchmark info
    core = ERC3(key=config.ERC3_API_KEY)
    info = core.view_benchmark(benchmark_name)
    
    # Build markdown content
    lines = [
        f"# {benchmark_name} Specs",
        "",
        f"**Benchmark ID:** {info.id}",
        f"**Description:** {info.description}",
        f"**Status:** {info.status}",
        f"**Total Tasks:** {len(info.specs)}",
        "",
        "---",
        "",
        "## Tasks",
        "",
    ]
    
    for i, spec in enumerate(info.specs):
        lines.append(f"### Task {i}: {spec.id}")
        lines.append("")
        lines.append(f"**Task:** {spec.task}")
        if spec.gotcha:
            lines.append(f"")
            lines.append(f"**Gotcha:** {spec.gotcha}")
        lines.append("")
        lines.append("---")
        lines.append("")
    
    # Add API routes section
    lines.append("## Available API Routes")
    lines.append("")
    for route in info.routes:
        lines.append(f"- `{route.path}`: {route.description}")
    lines.append("")
    
    # Write to file
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DOCS_DIR / f"{benchmark_name}_specs.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    
    print(f"✓ Specs exported to {output_path}")
    return output_path

