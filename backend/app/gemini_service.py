
"""
SiteGuardian Gemini Intelligence Service.

Gemini analyses recorded construction-site incidents.
It provides explanations and recommendations for human review.
It never controls physical alarms or safety equipment.
"""

import json
from collections import Counter
from typing import Any

from google import genai

from .config import GEMINI_API_KEY, GEMINI_MODEL


# Maximum number of incidents sent to Gemini.
MAX_INCIDENTS = 100


def convert_incident(event: Any) -> dict:
    """Convert an incident into a JSON-compatible dictionary."""

    if hasattr(event, "model_dump"):
        return event.model_dump(mode="json")

    if hasattr(event, "dict"):
        return event.dict()

    if isinstance(event, dict):
        return event

    raise ValueError("Unsupported incident format")


def get_incident_summary(events: list[dict]) -> dict:
    """
    Calculate factual statistics using Python.
    Gemini will interpret these statistics, not invent them.
    """

    hazard_counts = Counter()
    zone_counts = Counter()
    severity_counts = Counter()

    for event in events:
        hazard = event.get("hazard_type", "Unknown")
        zone = event.get("zone_id", "Unknown")
        severity = event.get("severity", "Unknown")

        hazard_counts[hazard] += 1
        zone_counts[zone] += 1
        severity_counts[severity] += 1

    total = len(events)

    def calculate_percentages(counter):
        return {
            name: {
                "count": count,
                "percentage": round((count / total) * 100, 1)
            }
            for name, count in counter.most_common()
        } if total else {}

    return {
        "total_incidents": total,
        "hazards": calculate_percentages(hazard_counts),
        "zones": calculate_percentages(zone_counts),
        "severity": calculate_percentages(severity_counts)
    }


def build_analysis_prompt(
    events: list[dict],
    evidence: dict
) -> str:
    """Build the instructions and evidence sent to Gemini."""

    incident_data = json.dumps(
        events,
        indent=2,
        default=str
    )

    statistics = json.dumps(
        evidence,
        indent=2
    )

    return f"""
You are SiteGuardian AI, a construction-site incident
analysis assistant.

Your responsibility is to analyse recorded incident
history and provide useful preventive recommendations
for qualified human supervisors.

IMPORTANT SAFETY RULES:

1. Only use the incident records and statistics supplied.
2. Never invent incidents, locations, dates or counts.
3. Distinguish observed facts from possible explanations.
4. Never claim that a correlation proves a cause.
5. Recommendations must be connected to actual evidence.
6. If the evidence is insufficient, clearly say so.
7. Never control physical alarms or safety equipment.
8. Never claim SiteGuardian is certified safety equipment.
9. Provide no more than three recommendations.
10. All recommendations require human review.

YOUR TASK:

Analyse the recorded incidents and identify:

1. The most frequently occurring hazard.
2. The most frequently affected zone.
3. Repeated patterns across the incident history.
4. Possible reasons that supervisors may wish to investigate.
5. Preventive recommendations supported by the evidence.

OUTPUT FORMAT:

SITEGUARDIAN SAFETY INSIGHT

SUMMARY:
Give a short explanation of the overall incident history.

MOST COMMON HAZARD:
Identify the hazard and its recorded count.

MOST AFFECTED ZONE:
Identify the zone and its recorded count.

OBSERVED PATTERNS:
List the recurring patterns supported by the data.

POSSIBLE CONCERNS:
Explain what supervisors might investigate.
Do not present possible causes as established facts.

RECOMMENDATIONS:
Provide up to three practical recommendations.
Explain the evidence supporting each recommendation.

LIMITATIONS:
Explain any important limitations in the available data.

HUMAN REVIEW:
State that a qualified supervisor must review
all recommendations.

VERIFIED STATISTICS:
{statistics}

RECORDED INCIDENTS:
{incident_data}

Analyse only the supplied information.
"""


def analyze_incidents(events: list[dict]) -> str:
    """
    Analyse actual stored incidents using Gemini.

    Returns a natural-language safety insight.
    Raises RuntimeError if Gemini is unavailable.
    """

    if not events:
        raise RuntimeError("There are no incidents to analyse.")

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. "
            "Add your API key to the local .env file."
        )

    try:
        # Convert the records into dictionaries.
        incidents = [
            convert_incident(event)
            for event in events[:MAX_INCIDENTS]
        ]

        # Calculate verified statistics.
        evidence = get_incident_summary(incidents)

        # Prepare the Gemini prompt.
        prompt = build_analysis_prompt(
            incidents,
            evidence
        )

        # Connect to Gemini.
        client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        # Request the analysis.
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        if not response.text:
            raise RuntimeError(
                "Gemini returned an empty response."
            )

        return response.text.strip()

    except RuntimeError:
        raise

    except Exception as exc:
        raise RuntimeError(
            "Gemini analysis is currently unavailable."
        ) from exc
