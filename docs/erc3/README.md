# ERC3 Benchmark Documentation

This folder contains reference documentation for ERC3 benchmark variants.

## Files

- `erc3-dev_specs.md` - Development benchmark specs
- `erc3-test_specs.md` - Test benchmark specs  
- `erc3_specs.md` - Final competition specs (when available)

## Generating Specs

To regenerate specs documentation:

```python
from benchmarks.erc3.wiki import export_specs_info

export_specs_info("erc3-dev")
export_specs_info("erc3-test")
export_specs_info("erc3")
```

## Purpose

These files help during agent development by providing:
- Quick reference for task descriptions
- Gotchas/hints for tricky tasks
- Available API routes

