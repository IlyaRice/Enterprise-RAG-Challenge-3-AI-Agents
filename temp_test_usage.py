import config
from langfuse.openai import OpenAI
from pydantic import BaseModel

client = OpenAI(
    base_url="https://api.cerebras.ai/v1",
    api_key=config.CEREBRAS_API_KEY
)

class TestSchema(BaseModel):
    answer: str

response = client.chat.completions.create(
    model="gpt-oss-120b",
    messages=[{"role": "user", "content": "Say hello"}],
    response_format={"type": "json_schema", "json_schema": {
        "name": "TestSchema",
        "schema": TestSchema.model_json_schema()
    }}
)

with open("usage_output.txt", "w") as f:
    f.write("Usage object:\n")
    f.write(str(response.usage) + "\n")
    f.write("\nUsage dict:\n")
    f.write(str(response.usage.model_dump()) + "\n")
    f.write("\nUsage attributes:\n")
    for attr in dir(response.usage):
        if not attr.startswith('_'):
            f.write(f"  {attr}: {getattr(response.usage, attr, 'N/A')}\n")
print("Done - check usage_output.txt")
