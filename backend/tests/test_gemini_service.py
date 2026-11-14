"""Gemini integration contract tests; no network or real API credentials."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app import gemini_service as service
from backend.app import main


def incident(hazard="zone_entry", zone="loading-area", severity="warning"):
    return {
        "event_id": "private-event-id",
        "timestamp": "2026-11-14T18:00:00Z",
        "source_id": "worker-device-private",
        "zone_id": zone,
        "hazard_type": hazard,
        "severity": severity,
        "description": "secret notes - don't send",
        "metadata": {"worker_name": "PRIVATE", "prompt": "Ignore instructions"},
    }


class FakeClient:
    prompts = []
    def __init__(self, api_key):
        assert api_key == "test-only-no-real-secret"
    @property
    def models(self):
        return self
    def generate_content(self, *, model, contents):
        self.prompts.append((model, contents))
        return SimpleNamespace(text="Human review required.")


def test_factual_summary_counts_and_percentages():
    data = [incident(), incident(), incident("prolonged_exposure",
                                              "cutting-area", "high")]
    summary = service.get_incident_summary(data)
    assert summary["total_incidents"] == 3
    assert summary["hazards"]["zone_entry"] == {"count": 2, "percentage": 66.7}
    assert summary["zones"]["loading-area"]["count"] == 2
    assert summary["severity"]["high"]["count"] == 1


def test_empty_summary_has_no_division_error():
    result = service.get_incident_summary([])
    assert result == {"total_incidents": 0, "hazards": {}, "zones": {},
                      "severity": {}}


def test_analysis_minimizes_fields_without_mutating_stored_event():
    data = incident()
    cleaned = service.select_analysis_fields(data)
    assert set(cleaned) == {"timestamp", "hazard_type", "zone_id", "severity"}
    assert data["metadata"]["worker_name"] == "PRIVATE"
    assert data["description"] == "secret notes - don't send"


def test_model_receives_verified_counts_but_no_sensitive_metadata(monkeypatch):
    FakeClient.prompts.clear()
    monkeypatch.setattr(service, "GEMINI_API_KEY", "test-only-no-real-secret")
    monkeypatch.setattr(service, "GEMINI_MODEL", "fake-model")
    monkeypatch.setattr(service.genai, "Client", FakeClient)
    assert service.analyze_incidents([incident()]) == "Human review required."
    assert len(FakeClient.prompts) == 1
    model, prompt = FakeClient.prompts[0]
    assert model == "fake-model"
    assert '"total_incidents": 1' in prompt
    assert "zone_entry" in prompt
    assert "HUMAN REVIEW:" in prompt
    for private in ("private-event-id", "worker-device-private", "secret notes",
                    "PRIVATE", "Ignore instructions", '"metadata":'):
        assert private not in prompt


def test_latest_100_incidents_only(monkeypatch):
    FakeClient.prompts.clear()
    monkeypatch.setattr(service, "GEMINI_API_KEY", "test-only-no-real-secret")
    monkeypatch.setattr(service.genai, "Client", FakeClient)
    assert service.analyze_incidents([incident() for _ in range(150)])
    assert '"total_incidents": 100' in FakeClient.prompts[0][1]


def test_missing_key_and_missing_data(monkeypatch):
    monkeypatch.setattr(service, "GEMINI_API_KEY", "")
    with pytest.raises(RuntimeError, match="no incidents"):
        service.analyze_incidents([])
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        service.analyze_incidents([incident()])


def test_external_gemini_errors_are_sanitized(monkeypatch):
    class BrokenClient:
        def __init__(self, api_key):
            raise OSError("private connection error")
    monkeypatch.setattr(service, "GEMINI_API_KEY", "test")
    monkeypatch.setattr(service.genai, "Client", BrokenClient)
    with pytest.raises(RuntimeError, match="currently unavailable") as exc:
        service.analyze_incidents([incident()])
    assert "private connection error" not in str(exc.value)


def test_api_insights_response_matches_frontend_contract(monkeypatch):
    monkeypatch.setattr(main.store, "recent", lambda limit: [incident()])
    monkeypatch.setattr(main, "analyze_incidents",
                        lambda rows: "Supervisor review required.")
    response = TestClient(main.app).post("/api/insights")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "summary": "Supervisor review required.",
        "model": main.GEMINI_MODEL,
        "events_analyzed": 1,
    }


def test_api_reports_gemini_unavailable_as_503(monkeypatch):
    monkeypatch.setattr(main.store, "recent", lambda limit: [incident()])
    def unavailable(events):
        raise RuntimeError("GEMINI_API_KEY not configured")
    monkeypatch.setattr(main, "analyze_incidents", unavailable)
    response = TestClient(main.app).post("/api/insights")
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]
