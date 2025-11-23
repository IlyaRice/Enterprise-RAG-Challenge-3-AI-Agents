# Installation

## Prerequisites
- Python 3.12 or higher
- pip (Python package installer)

## Setup
1. Clone the repository
```bash
git clone https://github.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents.git
cd Enterprise-RAG-Challenge-3-AI-Agents
```

2. Create and activate a virtual environment
```bash
# On Windows
python -m venv .venv
.venv\Scripts\activate

# On macOS/Linux
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

## Environment Configuration
1. Create an `.env` file in the project root (copy from `.env.example`)
```bash
# On Windows
copy .env.example .env

# On macOS/Linux
cp .env.example .env
```

2. Edit the `.env` file with your API keys and configuration
