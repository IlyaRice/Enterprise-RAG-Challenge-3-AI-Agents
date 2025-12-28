# Installation

## Prerequisites
- Python 3.12 or higher
- pip (Python package installer)
- ERC3 API key (get it at https://erc.timetoact-group.at/)
- LLM provider API key (OpenRouter or Cerebras)
- Node.js v18 or higher (optional - only for trace visualizer)

## Setup

### 1. Clone the Repository
```bash
git clone https://github.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents.git
cd Enterprise-RAG-Challenge-3-AI-Agents
```

### 2. Create Virtual Environment (Recommended)
```bash
python -m venv .venv
source .venv/bin/activate # or .venv\Scripts\activate on Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## Configuration

### 1. Create Environment File
Copy `.env.example` to `.env`:
```bash
cp .env.example .env # or copy .env.example .env on Windows
```

### 2. Configure API Keys

Edit `.env` and set the following **required** variables:

```bash
# Required
ERC3_API_KEY=your_erc3_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
LANGFUSE_TRACING_ENABLED=0
```

**Optional variables:**
- `CEREBRAS_API_KEY` - Direct Cerebras API access (alternative to OpenRouter)
- `USER_NAME` - Prefix for session names in dashboard
- `LOCAL_DEV` - Set to `1` to prioritize .env over system environment
- `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_BASE_URL` - LLM observability setup

### LLM Provider Notes

**OpenRouter** (recommended): Works reliably for all tasks. Use this unless you have specific requirements.

**Cerebras**: Direct API access needed if you want to use `reasoning_effort` parameter (ignored when routing through OpenRouter).

## Verify Installation

Test with a single task:
```bash
python main.py erc3-dev --tasks 1 -v
```

Expected output: Task execution with detailed logs (verbose mode), ending with score and completion message.

## Trace Visualizer

### Live Version (No Setup)

**[Open the visualizer](https://ilyarice.github.io/Enterprise-RAG-Challenge-3-AI-Agents/)** - runs in your browser, no installation needed.

The visualizer has three tabs in the left sidebar:
- **Tasks** - View the execution tree and details for the current trace
- **Demos** - Pre-loaded demo traces
- **Files** - Browse traces from your local `traces/` folder or upload individual files

### Local Setup (Optional)

Only needed if you want to modify the visualizer code or keep everything offline.

#### Installation

```bash
cd trace-viewer
npm install
```

### Usage

```bash
cd trace-viewer
npm run dev
```

Open http://localhost:3000 in your browser.