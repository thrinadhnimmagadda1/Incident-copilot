import pytest

from import_runbooks import validate


def test_import_adds_source_citation():
    record = {
        "id": "INC-100", "title": "Example", "log_pattern": "error",
        "system": "Example", "symptoms": "failure", "root_cause": "cause",
        "fix": "fix", "severity": "low", "resolution_time_minutes": 5,
    }
    assert validate(record, "runbook.json")["source"] == "runbook.json"


def test_import_rejects_incomplete_record():
    with pytest.raises(ValueError):
        validate({"id": "INC-100"}, "broken.json")
