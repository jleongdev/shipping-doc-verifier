import json
import anthropic
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY

# Main model for extraction, cheaper model for classification.
MODEL_MAIN = "claude-sonnet-5"
MODEL_CHEAP = "claude-haiku-4-5"


class LLMError(Exception):
    pass


def complete_json(
    system: str,
    user: str,
    *,
    model: str = MODEL_MAIN,
    max_tokens: int = 1024
) -> dict:
    """Call Claude and parse a JSON object from its reply.

    The SDK already retries network/429/5xx errors.
    We add one retry for malformed or unexpected JSON output.
    """
    last_text = ""

    for _ in range(2):
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": user
                }
            ],
        )

        last_text = next(
            (block.text for block in resp.content if block.type == "text"),
            ""
        )

        try:
            cleaned = last_text.strip()

            # Handle Markdown fenced JSON safely.
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()

                # Remove opening fence only if there is actual content after it.
                if len(lines) > 1:
                    lines = lines[1:]

                    # Remove closing fence if present.
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]

                    cleaned = "\n".join(lines).strip()

            parsed = json.loads(cleaned)

            # complete_json promises to return a dict.
            if not isinstance(parsed, dict):
                raise ValueError("Model returned JSON that is not an object")

            return parsed

        except (json.JSONDecodeError, ValueError, TypeError):
            user += (
                "\n\nReturn ONLY one valid JSON object. "
                "Do not use Markdown code fences or additional text."
            )

    raise LLMError(
        f"Model did not return a valid JSON object:\n{last_text}"
    )