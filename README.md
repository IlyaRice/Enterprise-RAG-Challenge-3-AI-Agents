# Enterprise RAG Challenge 3: AI Agents

**Competition Results:** 🥇 1st place in local models category, 🥈 2nd place overall

This repository contains my implementation of AI agents for the [ERC 3](https://erc.timetoact-group.at/) competition. The challenge involves building autonomous agents that can navigate complex enterprise systems, retrieve information from internal wikis, and execute operations through API calls while following strict business rules.

The implementation features a Plan ReAct agent architecture with pre-execution step validation and dynamic context selection.

## Disclaimer

This is competition code - it works, but has rough edges. A few things to know:

- The ERC3 API integration is competition-specific (you'll need your own ERC3 API key for access to the benchmark platform)
- You'll need API keys for OpenRouter/Cerebras
- Some features are implemented but not used (looking at you, overengineered wiki search)
- The trace visualizer requires Node.js and npm (but it's optional)

If you're looking for production-ready code, this isn't it. But if you want to explore agent architectures and their implementation - dive in!

## Getting Started

**[Installation Guide](docs/installation.md)** - Setup instructions, API configuration, and trace visualizer setup

## Usage

Available benchmarks: `store`, `erc3-dev`, `erc3-test`, `erc3-prod`

```bash
# Session mode (creates dashboard session)
python main.py <benchmark>

# Task mode (development/testing)
python main.py <benchmark> --tasks <indices>

# Options:
  -t, --tasks     Task indices or "all"
  -r, --runs      Number of runs per task (consistency testing)
  -v, --verbose   Enable verbose output
  -w, --workers   Max parallel workers (default: auto)
  -h, --help      Show help message
```

## How It Works

### The Big Picture

**One-time setup (ingestion):**

There's a preparation script that downloads all unique wikis from benchmark tasks (identified by SHA1 from whoami) and caches them locally. Then it uses an LLM with validation to extract two types of rules from each wiki: one set for public users, another for authenticated users. Response formatting instructions get extracted separately.

To save you time, I've included the ingestion results in the repo (`benchmarks/erc3/wiki_data/`), so you don't need to run this step. But if you're curious, the ingestion code is in `benchmarks/erc3/ingestion/`.

By the way, if you want to see detailed info about the tasks, check out the [ERC3 Specs](docs/erc3/) - I exported them during ingestion for easier reference.

**When running a task:**

Before the agent even starts, we do some prep work:
- Call `whoami` to figure out if we're dealing with a public or authenticated user
- For authenticated users: grab their full profile, projects, managed customers, and time entries via SDK
- Use an LLM to pick only the relevant context blocks for this specific task
- Build the agent's system prompt with the right rules (public or authenticated)

Then we run the agent in a loop until it calls the final `/respond` tool.

### Agent Architecture

**Preparing the agent's system prompt:**

The system prompt contains base operating rules and tool descriptions. We load user-specific rules (public or authenticated) based on whoami results. All SDK tools are wrapped with auto-pagination and error handling.

**The agent loop:**

The agent uses a Plan ReAct architecture with fully structured output (via Pydantic schemas). At each step, the agent writes:
- `current_state` - what we know so far (who the user is, what data we have, etc.)
- `remaining_work` - plan of remaining actions (up to 5 items)
- `next_action` - description and reasoning for the next step
- `function` - specific SDK tool to call (or `/respond` to finish)

When the agent chooses the `/respond` tool, that's the final answer - the loop terminates. Right before calling `/respond`, the agent loads response formatting rules via `/load-respond-instructions`.

**Step validation:**

Here's the interesting bit - every step gets validated *before* the tool is actually executed. A step validator checks:
- Is this the right tool for the job?
- Are the parameters correct?
- Are we following all the rules?

If something's off, the validator rejects the step with an explanation, and the agent regenerates that step with the feedback in mind. No bad moves get through.

**Conversation management:**

The main conversation only logs successful, executed steps. Everything else is ephemeral:
- Validation rejections and retry feedback live in a temporary conversation that gets discarded after retry
- Validator internal analysis never enters the agent's history
- Agent's structured output gets compressed to action summary + tool call + result

Plan continuity: the conversation preserves only the latest "remaining_work" plan. The agent sees what it planned last time and can iterate on it - update based on new data or keep it similar. Older plans get dropped automatically, so we don't accumulate a history of outdated plans.

The agent sees only what matters: the successful execution path, not validation loops or reasoning dumps.
Less clutter means the agent makes better decisions based on what actually happened.

### Store Benchmark Architecture

Note: `store` was a warm-up benchmark with different dynamics. That's why the main ERC3 benchmarks use a completely different architecture (the one described above). But the store approach is still interesting, so here's a quick overview:

The store benchmark uses a multi-agent system with delegation:

**Orchestrator** coordinates the task and delegates subtasks to specialized sub-agents:
- **ProductExplorer** - analyzes the product catalog (single LLM call with full catalog)
- **BasketBuilder** - manages basket contents and applies coupons (agent loop with basket tools)
- **CheckoutProcessor** - handles checkout and customer data (agent loop with checkout tools)

Each sub-agent runs independently with its own set of relevant sdk tools and validation. The orchestrator collects their reports and either delegates more work or submits the final answer. It's a hierarchical architecture where each agent focuses on what it does best.

### Side Notes

- Rule extraction from wikis also uses a validator (up to 4 attempts to get it right)
- Langfuse tracing everywhere - super helpful for debugging
- Task mode lets you run specific tasks by index - great for development
- Custom trace export to JSON files with web-based visualizer for execution analysis
- The visualizer includes demo traces - just run `cd trace-viewer && npm install && npm run dev` and click the "Demos" tab to study agent behavior without any API keys or Python setup
- Consistency testing: run the same tasks multiple times and get distribution graph
- Lots of parallel execution for speed
- Hybrid BM25 + Fuzzy Wiki Search is implemented but not actually used (didn't get around to it)

## Project Structure

```
Enterprise-RAG-Challenge-3-AI-Agents/
├── main.py                 # CLI entry point
├── ai_agent.py            # Agent routing
├── infrastructure.py      # Core utilities (LLM calls, tracing, retries)
├── erc_utilities.py       # Benchmark execution and visualization
├── benchmarks/
│   ├── erc3/              # ERC3 benchmark implementation
│   │   ├── runner.py      # Main benchmark coordinator
│   │   ├── runtime/       # Agent loop, tools, context building
│   │   ├── ingestion/     # Wiki download and rule extraction
│   │   └── wiki_data/     # Cached wiki files
│   └── store/             # Store benchmark (orchestrator + sub-agents)
├── trace-viewer/          # Interactive web-based trace visualization
├── traces/                # Generated trace JSON files
└── docs/                  # Documentation
```

## License

MIT