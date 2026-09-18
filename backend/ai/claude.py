import json
import anthropic
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY

# You picked Sonnet as the main model. Haiku is a cheap option for the
# high-volume classify step; keep Sonnet for extraction accuracy.
MODEL_MAIN = "claude-sonnet-5"
MODEL_CHEAP = "claude-haiku-4-5"


class LLMError(Exception):
    pass


def complete_json(system: str, user: str, *, model: str = MODEL_MAIN,
                  max_tokens: int = 1024) -> dict:
    """Call Claude and parse a JSON object from its reply.
    The SDK already retries network/429/5xx. We add one retry for bad JSON."""
    last_text = ""
    for _ in range(2):
        resp = client.messages.create(
            model=model, max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        last_text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            return json.loads(last_text)
        except json.JSONDecodeError:
            user += "\n\nReturn ONLY valid JSON, nothing else."
    raise LLMError(f"Model did not return valid JSON:\n{last_text}")
