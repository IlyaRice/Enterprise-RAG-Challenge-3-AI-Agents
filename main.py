#!/usr/bin/env python3
"""
Enterprise RAG Challenge - Benchmark Runner

Run AI agent benchmarks in session mode or individual task mode.

MODE OVERVIEW:
- Session mode: Creates a session in your "My sessions" dashboard and runs the full benchmark
- Task mode: Runs specific tasks independently without creating a session, useful for:
  * Testing individual tasks during development
  * Consistency/reliability testing by running tasks multiple times
  * Debugging specific scenarios
  * Shows a GUI plot with score distribution at the end
"""

import argparse
import sys
import config
from erc_utilities import repeat_tasks, create_and_run_session, TaskResult, RunResult

# Task definitions for each benchmark
BENCHMARK_TASKS = {
    'store': list(range(15)),        # 0-14
    'erc3-dev': list(range(16)),     # 0-15
    'erc3-test': list(range(24)),    # 0-23
    'erc3-prod': list(range(103)),   # 0-102
}


def parse_task_indices(task_args, benchmark):
    """
    Parse task indices from command line arguments.
    
    Args:
        task_args: List of task arguments (can contain 'all' or integers)
        benchmark: Benchmark name to get all tasks for
        
    Returns:
        List of task indices
    """
    if not task_args:
        return None
    
    # Handle "all" keyword
    if len(task_args) == 1 and task_args[0].lower() == 'all':
        if benchmark in BENCHMARK_TASKS:
            return BENCHMARK_TASKS[benchmark]
        else:
            print(f"Warning: 'all' keyword not defined for benchmark '{benchmark}'")
            print("Please specify task indices explicitly or update BENCHMARK_TASKS in main.py")
            sys.exit(1)
    
    # Parse individual task indices
    try:
        return [int(task) for task in task_args]
    except ValueError:
        print(f"Error: Task indices must be integers or 'all', got: {task_args}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Run AI agent benchmarks in session or task mode',
        epilog='''
modes:
  Session mode (default):
    - Creates a session in your "My sessions" dashboard
    - Runs the complete benchmark sequence
    - Used for official benchmark runs
  
  Task mode (--tasks specified):
    - Runs specific tasks independently without creating a session
    - Useful for development, debugging, and consistency testing
    - Displays a GUI plot showing score distribution at the end

examples:
  # Session mode - creates dashboard session
  %(prog)s store
  %(prog)s erc3-prod -v
  
  # Task mode - test specific tasks without session
  %(prog)s store -t 1 2 6 7 8
  %(prog)s erc3-test --tasks 7 8 11 13
  
  # Consistency testing - multiple runs with visualization
  %(prog)s store -t 2 12 -r 5
  %(prog)s erc3-test -t 7 8 11 13 17 18 21 22 23 -r 5 -w 10
  
  # Run all tasks (useful for full reliability testing)
  %(prog)s store -t all -r 5
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Positional argument
    parser.add_argument(
        'benchmark',
        choices=['store', 'erc3-test', 'erc3-dev', 'erc3-prod'],
        help='Benchmark to run'
    )
    
    # Optional arguments
    parser.add_argument(
        '--tasks', '-t',
        nargs='+',
        metavar='INDEX',
        help='Task indices to run (space-separated) or "all" for all tasks. '
             'Enables task mode (no session created). '
             'If not specified, runs full session mode with dashboard tracking.'
    )
    
    parser.add_argument(
        '--runs', '-r',
        type=int,
        default=1,
        metavar='N',
        help='Number of times to run each task (default: 1). '
             'Only applies to task mode for consistency testing. '
             'Ignored in session mode.'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--workers', '-w',
        type=int,
        metavar='N',
        help='Max parallel workers (default: auto - runs count for task mode, 10 for session mode)'
    )
    
    args = parser.parse_args()
    
    # Set config
    config.VERBOSE = 1 if args.verbose else 0
    config.MAX_WORKERS = args.workers
    
    # Parse task indices
    task_indices = parse_task_indices(args.tasks, args.benchmark)
    
    # Execute based on mode
    if task_indices is None:
        # Session mode
        if args.runs > 1:
            print(f"Warning: --runs flag is ignored in session mode (running full session)")
        
        print(f"\n{'='*60}")
        print(f"SESSION MODE")
        print(f"Benchmark: {args.benchmark}")
        print(f"Creating session in dashboard...")
        print(f"{'='*60}\n")
        result = create_and_run_session(
            benchmark=args.benchmark
        )
    else:
        # Task mode
        print(f"\n{'='*60}")
        print(f"TASK MODE (no session created)")
        print(f"Benchmark: {args.benchmark}")
        print(f"Tasks: {task_indices}")
        print(f"Runs per task: {args.runs}")
        print(f"Note: Score distribution chart will appear after completion")
        print(f"{'='*60}\n")
        result = repeat_tasks(
            benchmark=args.benchmark,
            task_indices=task_indices,
            num_times=args.runs
        )
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Results Summary:")
    print(f"  Benchmark: {result.meta.benchmark}")
    print(f"  Score: {result.meta.total_score}/{result.meta.num_tasks}")
    print(f"  Average: {result.meta.avg_score:.2f}")
    print(f"  Tasks: {result.meta.task_indices}")
    if hasattr(result.meta, 'num_runs') and result.meta.num_runs > 1:
        print(f"  Runs per task: {result.meta.num_runs}")
    if result.meta.session_id:
        print(f"  Session: https://erc.timetoact-group.at/sessions/{result.meta.session_id}")
    print(f"{'='*60}\n")
    
    return result


if __name__ == "__main__":
    result = main()
