"""Gemini is strictly advisory: it never controls physical alarms."""
import json
from google import genai
from .config import GEMINI_API_KEY, GEMINI_MODEL

GUIDANCE = """You analyse incidents from a construction-site HACKATHON PROTOTYPE.
Summarise verified counts and common zones/hazards from supplied JSON only.
Suggest at most three preventive actions for qualified supervisors to consider.
Distinguish observations from speculation; flag sparse samples.
Never imply the product is a certified safety system.
Do not invent specific sensor evidence or unsafe instructions."""

def analyze_incidents(events: list[dict]) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not configured; add it to your local .env.")
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=GUIDANCE + "\n\nRecorded incidents:\n" + json.dumps(events[:100], default=str),
    )
    if not response.text:
        raise RuntimeError("Gemini returned no analysis")
    return response.text
