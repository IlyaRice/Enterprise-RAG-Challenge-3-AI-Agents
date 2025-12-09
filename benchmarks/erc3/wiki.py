"""
Wiki ingestion and preprocessing for ERC3 benchmarks.

Downloads and caches wiki files for erc3, erc3-dev, and erc3-test benchmarks.
Wikis are stored in wiki_data/{sha1_prefix}/ - shared across benchmarks since
wikis with the same SHA are identical regardless of which benchmark uses them.

Also provides benchmark metadata export for development reference.

Usage:
    from benchmarks.erc3.wiki import ingest_wikis, tag_wiki_files, export_specs_info
    
    ingest_wikis("erc3-dev")       # Download erc3-dev wikis
    tag_wiki_files(wiki_dir)       # Tag files with has_rules
    export_specs_info("erc3-dev")  # Export specs to docs/erc3/
"""

import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
from erc3 import ERC3, TaskInfo
from erc3.erc3.dtos import Req_ListWiki, Req_LoadWiki, Req_WhoAmI, Req_ListEmployees, Req_GetEmployee
from langfuse import observe
from infrastructure import call_llm
from .prompts import TaggingResponse, ValidatorResponse, tagging_prompt, validator_prompt
from .tools import _paginate
import config

# Path to wiki data directory (relative to this file)
WIKI_DATA_DIR = Path(__file__).parent / "wiki_data"

# Path to docs directory (project root)
DOCS_DIR = Path(__file__).parent.parent.parent / "docs" / "erc3"


def get_wiki_data_path(sha1_prefix: str = None) -> Path:
    """
    Get path to wiki data directory.
    
    Args:
        sha1_prefix: Optional 8-char sha1 prefix for specific wiki version
    
    Returns:
        Path to wiki data directory or specific wiki version folder
    """
    if sha1_prefix:
        return WIKI_DATA_DIR / sha1_prefix
    return WIKI_DATA_DIR


def _download_wiki_files(client, wiki_dir: Path, wiki_sha1: str, benchmark_name: str, tasks: list):
    """
    Download all wiki files and create wiki_meta.
    
    Args:
        client: SDK client for API calls
        wiki_dir: Directory to save wiki files
        wiki_sha1: Full SHA1 hash of the wiki
        benchmark_name: Name of the benchmark
        tasks: List of task dicts with index, id, task, gotcha
    """
    list_response = client.dispatch(Req_ListWiki())
    wiki_paths = list_response.paths
    
    print(f"  Found {len(wiki_paths)} wiki files")
    
    wiki_meta = {
        "sha1": wiki_sha1,
        "tasks": {
            benchmark_name: tasks
        },
        "files": []
    }
    
    def download_single_file(wiki_path):
        """Download a single wiki file."""
        print(f"    Downloading: {wiki_path}")
        load_response = client.dispatch(Req_LoadWiki(file=wiki_path))
        
        file_path = wiki_dir / wiki_path.replace("/", "_")
        file_path.write_text(load_response.content, encoding="utf-8")
        
        return {
            "path": wiki_path,
            "saved_as": file_path.name
        }
    
    # Download files in parallel with 40 workers
    with ThreadPoolExecutor(max_workers=40) as executor:
        futures = {executor.submit(download_single_file, wiki_path): wiki_path for wiki_path in wiki_paths}
        
        for future in as_completed(futures):
            try:
                file_info = future.result()
                wiki_meta["files"].append(file_info)
            except Exception as e:
                wiki_path = futures[future]
                print(f"    ✗ Error downloading {wiki_path}: {str(e)}")
    
    (wiki_dir / "wiki_meta.json").write_text(json.dumps(wiki_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓ Wiki exported to {wiki_dir}")


def ingest_wikis(benchmark_name: str):
    """
    Iterate through all tasks in a benchmark, check wiki sha1 from whoami,
    and download wikis that haven't been cached yet.
    
    Args:
        benchmark_name: Name of the benchmark (e.g., "erc3-dev", "erc3-test", "erc3")
    """
    # Validate benchmark name
    if not benchmark_name.startswith("erc3"):
        raise ValueError(f"Wiki ingestion only supports erc3* benchmarks, got: {benchmark_name}")
    
    # Initialize ERC3 client
    core = ERC3(key=config.ERC3_API_KEY)
    benchmark_info = core.view_benchmark(benchmark_name)
    
    print(f"Processing {len(benchmark_info.specs)} specs in benchmark '{benchmark_name}'")
    
    # Cache for task clients (to avoid recreating for each spec)
    task_cache = {}
    
    def get_task_client(spec_idx: int, spec):
        """Create task and get client for a spec."""
        if spec_idx in task_cache:
            return task_cache[spec_idx]
        
        resp = core.start_new_task(benchmark=benchmark_name, spec_id=spec.id)
        detail = core.task_detail(resp.task_id)
        
        task_info = TaskInfo(
            spec_id=spec.id,
            task_id=resp.task_id,
            num=spec_idx,
            task_text=detail.text,
            status=resp.status,
            benchmark=benchmark_name,
            score=0.0
        )
        
        client = core.get_erc_dev_client(task_info)
        task_cache[spec_idx] = (client, task_info)
        return client, task_info
    
    # Step 1: Collect all sha1 hashes in parallel
    # Maps sha1 -> {"tasks": [...], "hash_prefix": str, "client": client}
    sha1_to_data = {}
    
    def get_sha1_for_spec(spec_idx, spec):
        """Get sha1 for a single spec."""
        try:
            client, task_info = get_task_client(spec_idx, spec)
            whoami_response = client.dispatch(Req_WhoAmI())
            wiki_sha1 = whoami_response.wiki_sha1
            hash_prefix = wiki_sha1[:8]
            
            task_data = {
                "index": spec_idx,
                "id": spec.id,
                "task": spec.task,
                "gotcha": spec.gotcha
            }
            return (spec_idx, wiki_sha1, hash_prefix, client, task_data)
        except Exception as e:
            print(f"  ✗ Error getting sha1 for {spec.id}: {str(e)}")
            return None
    
    print("\nStep 1: Collecting wiki SHA1 hashes in parallel...")
    with ThreadPoolExecutor(max_workers=25) as executor:
        futures = {executor.submit(get_sha1_for_spec, spec_idx, spec): spec_idx 
                   for spec_idx, spec in enumerate(benchmark_info.specs)}
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                spec_idx, wiki_sha1, hash_prefix, client, task_data = result
                print(f"  [{spec_idx + 1}/{len(benchmark_info.specs)}] {task_data['id']} -> {hash_prefix}")
                
                # Collect ALL specs per sha1
                if wiki_sha1 not in sha1_to_data:
                    sha1_to_data[wiki_sha1] = {
                        "tasks": [],
                        "hash_prefix": hash_prefix,
                        "client": client
                    }
                sha1_to_data[wiki_sha1]["tasks"].append(task_data)
    
    print(f"\nFound {len(sha1_to_data)} unique wiki versions")
    
    # Step 2: Download wikis or update existing wiki_metas
    print("\nStep 2: Processing wikis...")
    downloaded_count = 0
    updated_count = 0
    
    for wiki_sha1, data in sha1_to_data.items():
        hash_prefix = data["hash_prefix"]
        tasks = sorted(data["tasks"], key=lambda t: t["index"])  # Sort by index
        client = data["client"]
        
        wiki_dir = get_wiki_data_path(hash_prefix)
        wiki_meta_path = wiki_dir / "wiki_meta.json"
        
        # Check if wiki already exists
        if wiki_meta_path.exists():
            # Load existing wiki_meta and check if this benchmark is already there
            wiki_meta = json.loads(wiki_meta_path.read_text(encoding="utf-8"))
            existing_tasks = wiki_meta.get("tasks", {})
            
            if benchmark_name in existing_tasks:
                print(f"  {hash_prefix}: Already has {benchmark_name} tasks, skipping...")
                continue
            
            # Add tasks for this benchmark
            existing_tasks[benchmark_name] = tasks
            wiki_meta["tasks"] = existing_tasks
            wiki_meta_path.write_text(json.dumps(wiki_meta, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  {hash_prefix}: Added {len(tasks)} tasks for {benchmark_name}")
            updated_count += 1
            continue
        
        # Download new wiki
        print(f"  {hash_prefix}: Downloading ({len(tasks)} tasks in {benchmark_name})...")
        
        try:
            wiki_dir.mkdir(parents=True, exist_ok=True)
            _download_wiki_files(client, wiki_dir, wiki_sha1, benchmark_name, tasks)
            downloaded_count += 1
        except Exception as e:
            print(f"  ✗ Error downloading wiki {hash_prefix}: {str(e)}")
    
    print(f"\n✓ Completed! Downloaded {downloaded_count} new, updated {updated_count} existing")


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


# ============================================================================
# EMPLOYEE INDEX COLLECTION
# ============================================================================

def create_employee_index(wiki_sha1_prefix: str, force: bool = False) -> Path:
    """
    Collect all employees for a wiki and save to rules/employee_index.json.
    
    Tries multiple tasks if the employee list is empty (broken task).
    
    Args:
        wiki_sha1_prefix: 8-char SHA1 prefix of the wiki
        force: If True, overwrite existing employee_index.json
    
    Returns:
        Path to the created employee_index.json file
    
    Raises:
        ValueError: If no valid tasks found or all tasks return empty employee lists
        FileNotFoundError: If wiki directory doesn't exist
    """
    # Get wiki directory
    wiki_dir = get_wiki_data_path(wiki_sha1_prefix)
    if not wiki_dir.exists():
        raise FileNotFoundError(f"Wiki directory not found: {wiki_dir}")
    
    # Ensure rules directory exists
    rules_dir = wiki_dir / "rules"
    rules_dir.mkdir(exist_ok=True)
    output_path = rules_dir / "employee_index.json"
    
    # Check if already exists
    if output_path.exists() and not force:
        print(f"  Employee index already exists at {output_path} (use force=True to overwrite)")
        return output_path
    
    # Load wiki_meta to get tasks
    wiki_meta_path = wiki_dir / "wiki_meta.json"
    wiki_meta = json.loads(wiki_meta_path.read_text(encoding="utf-8"))
    
    # Get all tasks from all benchmarks
    all_tasks = []
    for benchmark_name, tasks in wiki_meta.get("tasks", {}).items():
        for task in tasks:
            all_tasks.append({
                "task": task,
                "benchmark": benchmark_name
            })
    
    if not all_tasks:
        raise ValueError(f"No tasks found in wiki_meta for {wiki_sha1_prefix}")
    
    print(f"Collecting employee index for wiki {wiki_sha1_prefix}...")
    print(f"  Found {len(all_tasks)} task(s) to try")
    
    # Try each task until we get a non-empty employee list
    core = ERC3(key=config.ERC3_API_KEY)
    employees = None
    
    for idx, task_data in enumerate(all_tasks):
        task = task_data["task"]
        benchmark_name = task_data["benchmark"]
        
        print(f"  Trying task {idx + 1}/{len(all_tasks)}: {task['id']} from {benchmark_name}...")
        
        try:
            # Create task and client
            resp = core.start_new_task(benchmark=benchmark_name, spec_id=task["id"])
            detail = core.task_detail(resp.task_id)
            
            task_info = TaskInfo(
                spec_id=task["id"],
                task_id=resp.task_id,
                num=task["index"],
                task_text=detail.text,
                status=resp.status,
                benchmark=benchmark_name,
                score=0.0
            )
            
            client = core.get_erc_dev_client(task_info)
            
            # Step 1: Get all employee IDs using pagination (EmployeeBrief only has basic fields)
            result = _paginate(client, Req_ListEmployees, "employees")
            
            if not result.get("complete"):
                print(f"    ⚠️ Warning: Employee list incomplete: {result.get('errors')}")
            
            employee_briefs = result.get("items", [])
            
            # Check if empty (broken task)
            if not employee_briefs:
                print(f"    ✗ Task returned empty employee list (broken task), trying next...")
                continue
            
            print(f"    ✓ Found {len(employee_briefs)} employees, fetching full details...")
            
            # Step 2: Get full details for each employee (EmployeeView has notes, skills, wills)
            employees = []
            for emp_brief in employee_briefs:
                emp_id = emp_brief.get("id")
                if not emp_id:
                    continue
                try:
                    resp = client.dispatch(Req_GetEmployee(id=emp_id))
                    if resp.employee:
                        employees.append(resp.employee.model_dump())
                except Exception as e:
                    print(f"    ⚠️ Failed to get employee {emp_id}: {e}")
            
            print(f"    ✓ Got full details for {len(employees)} employees")
            break
            
        except Exception as e:
            print(f"    ✗ Error with task: {str(e)}, trying next...")
            continue
    
    # Check if we got any employees
    if not employees:
        raise ValueError(f"All tasks returned empty employee lists for wiki {wiki_sha1_prefix}. This may indicate a systemic issue.")
    
    # Extract only the fields we want
    employee_index = []
    for emp in employees:
        skills = emp.get("skills", [])
        wills = emp.get("wills", [])
        
        employee_index.append({
            "id": emp.get("id"),
            "name": emp.get("name"),
            "department": emp.get("department"),
            "location": emp.get("location"),
            "notes": emp.get("notes", ""),
            "skills": [{"name": s["name"], "level": s["level"]} for s in skills],
            "wills": [{"name": w["name"], "level": w["level"]} for w in wills],
        })
    
    # Save to rules/employee_index.json
    output_path.write_text(
        json.dumps(employee_index, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    print(f"  ✓ Employee index saved to {output_path}")
    return output_path


def create_all_employee_indexes(force: bool = False):
    """
    Create employee indexes for all wiki versions.
    
    Args:
        force: If True, overwrite existing employee indexes
    """
    # Find all wiki directories
    wiki_dirs = []
    for wiki_dir in WIKI_DATA_DIR.iterdir():
        if not wiki_dir.is_dir():
            continue
        
        wiki_meta_path = wiki_dir / "wiki_meta.json"
        if not wiki_meta_path.exists():
            continue
        
        wiki_dirs.append(wiki_dir.name)
    
    if not wiki_dirs:
        print("No wiki versions found")
        return
    
    print(f"Creating employee indexes for {len(wiki_dirs)} wiki version(s)...\n")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for wiki_sha1_prefix in wiki_dirs:
        print(f"Processing wiki {wiki_sha1_prefix}:")
        try:
            result_path = create_employee_index(wiki_sha1_prefix, force=force)
            # Check if it was skipped (file existed)
            if not force and (WIKI_DATA_DIR / wiki_sha1_prefix / "rules" / "employee_index.json").exists():
                skip_count += 1
            else:
                success_count += 1
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            error_count += 1
        print()
    
    print(f"✓ Summary: {success_count} created, {skip_count} skipped, {error_count} errors")


# ============================================================================
# FILE TAGGING
# ============================================================================

@observe()
def tag_wiki_files(wiki_dir: str, max_attempts: int = 2) -> dict:
    """
    Tag wiki files with has_rules flag using LLM.
    
    Args:
        wiki_dir: Path to wiki directory containing wiki_meta.json
        max_attempts: Max validation retry attempts
    
    Returns:
        Dict with counts: {"tagged": N, "with_rules": M}
    """
    wiki_path = Path(wiki_dir)
    wiki_meta_path = wiki_path / "wiki_meta.json"
    
    if not wiki_meta_path.exists():
        raise FileNotFoundError(f"No wiki_meta.json in {wiki_dir}")
    
    wiki_meta = json.loads(wiki_meta_path.read_text(encoding="utf-8"))
    files = wiki_meta.get("files", [])
    
    if not files:
        return {"tagged": 0, "with_rules": 0}
    
    # Load all file contents
    file_contents = []
    for f in files:
        file_path = wiki_path / f["saved_as"]
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            file_contents.append(f'<file name="{f["saved_as"]}">\n{content}\n</file>')
    
    all_content = "\n\n".join(file_contents)
    original_user_message = f"Generate metadata for these wiki files:\n\n{all_content}"
    current_user_message = original_user_message
    
    last_result = None
    
    for attempt in range(1, max_attempts + 1):
        print(f"  Attempt {attempt}/{max_attempts}...")
        
        # Tag
        t_result = call_llm(
            schema=TaggingResponse,
            system_prompt=tagging_prompt,
            conversation=[{"role": "user", "content": current_user_message}],
            reasoning_effort="high",
        )
        t_parsed = t_result["parsed"]
        last_result = t_parsed
        
        # Count categories and rules
        files_with_rules = sum(1 for tag in last_result.files if tag.has_rules)
        category_counts = {}
        for tag in last_result.files:
            category_counts[tag.category] = category_counts.get(tag.category, 0) + 1
        
        print(f"    Tagged {len(last_result.files)} files:")
        print(f"      - {files_with_rules} with rules")
        print(f"      - Categories: {dict(category_counts)}")
        
        # Validate - format output as structured list
        formatted_output = "File Tags:\n"
        for tag in last_result.files:
            formatted_output += f"\n{tag.filename}:\n"
            formatted_output += f"  has_rules: {tag.has_rules}\n"
            formatted_output += f"  category: {tag.category}\n"
            formatted_output += f"  summary: {tag.summary}\n"
        
        validator_message = f"""TASK:
<system_prompt>
{tagging_prompt}
</system_prompt>

<user_prompt>
{original_user_message}
</user_prompt>

<result>
{formatted_output}
</result>

Validate this result with focus on:
1. PRIMARY (CRITICAL): Are has_rules flags accurate? Check for false positives (non-rule files marked as rules) and false negatives (rule files marked as non-rules).
2. SECONDARY: Are category assignments appropriate based on the category definitions in the system prompt?
3. SKIP: Do not validate summary quality - accept as-is.

Be especially rigorous about has_rules accuracy as this is the most critical field."""

        v_result = call_llm(
            schema=ValidatorResponse,
            system_prompt=validator_prompt,
            conversation=[{"role": "user", "content": validator_message}],
            reasoning_effort="high",
        )
        v_parsed = v_result["parsed"]
        print(f"    Validator: {'PASS' if v_parsed.is_valid else 'REJECT'}")
        
        if v_parsed.is_valid:
            break
        
        if attempt < max_attempts:
            print(f"    Rejection: {v_parsed.rejection_message}...")
            current_user_message = f"""{original_user_message}

RETRY: Previous attempt was rejected.

Previous output:
{formatted_output}

Rejection feedback: {v_parsed.rejection_message}

Address this feedback and try again."""
    
    # Update wiki_meta with all three fields
    for f in files:
        matching_tag = next((tag for tag in last_result.files if tag.filename == f["saved_as"]), None)
        if matching_tag:
            f["has_rules"] = matching_tag.has_rules
            f["category"] = matching_tag.category
            f["summary"] = matching_tag.summary
        else:
            print("No metadata generated for file: ", f["saved_as"])
            f["has_rules"] = False
            f["category"] = "human_flavor"
            f["summary"] = "No metadata generated"
    
    wiki_meta_path.write_text(json.dumps(wiki_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Count final stats
    files_with_rules_final = sum(1 for f in files if f.get("has_rules", False))
    category_counts_final = {}
    for f in files:
        cat = f.get("category", "unknown")
        category_counts_final[cat] = category_counts_final.get(cat, 0) + 1
    
    return {
        "tagged": len(files),
        "with_rules": files_with_rules_final,
        "categories": category_counts_final,
    }

