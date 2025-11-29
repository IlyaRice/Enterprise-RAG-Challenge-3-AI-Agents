import os
from dotenv import dotenv_values, load_dotenv

# Prioritize .env file variables over system environment when LOCAL_DEV=1
env_file_values = dotenv_values()
should_override = env_file_values.get("LOCAL_DEV") == "1"

load_dotenv(override=should_override)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ERC3_API_KEY = os.getenv("ERC3_API_KEY")
TRACES_EXPORT_PATH = os.getenv("TRACES_EXPORT_PATH")
# Debug/verbose mode - set to "1" in .env to enable detailed prints
VERBOSE = 0
