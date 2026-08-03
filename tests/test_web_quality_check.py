"""Web forge quality-check helpers and refine re-check."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.web

from agentforge.web.app import create_app
from agentforge.web.jobs import JobStore
from agentforge.web.routes.forge import (
    _attach_quality_check,
    _quality_check_payload,
    _resolve_check_domain,
    _skill_md_for_check,
    _truthy_form,
)

_GOOD_SKILL = """\
---
name: good-skill
description: A reasonably complete skill for check tests
---

# Good Skill

## Personality Profile
- Rigor 80%

## Key Responsibilities
- Ship reliable software

## Technical Skills
- Python

## Guardrails
- Never invent credentials
- Stay within domain scope
"""


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from agentforge.web import rate_limit

    rate_limit._limiter._requests.clear()


def test_truthy_form() -> None:
    assert _truthy_form("true")
    assert _truthy_form("1")
    assert _truthy_form("on")
    assert not _truthy_form("")
    assert not _truthy_form("false")
    assert _truthy_form(True)


def test_resolve_check_domain_explicit() -> None:
    assert _resolve_check_domain("data engineering", None) == "data engineering"


def test_resolve_check_domain_from_extraction_object() -> None:
    class Role:
        domain = "finance"

    class Ext:
        role = Role()

    assert _resolve_check_domain("auto", Ext()) == "finance"
    assert _resolve_check_domain("", Ext()) == "finance"


def test_resolve_check_domain_from_dict() -> None:
    extraction = {"role": {"domain": "security"}}
    assert _resolve_check_domain("", extraction) == "security"


def test_skill_md_prefers_skill_folder() -> None:
    result = {
        "skill_folder": {"skill_md": "folder", "skill_name": "a"},
        "clawhub_skill": {"skill_md": "claw", "skill_name": "b"},
    }
    md, path = _skill_md_for_check(result)
    assert md == "folder"
    assert path == "a/SKILL.md"


def test_quality_check_payload_structure() -> None:
    qc = _quality_check_payload(
        _GOOD_SKILL,
        "name: test\n",
        domain="general",
        strict=False,
        skill_path="good/SKILL.md",
    )
    assert qc is not None
    assert "passed" in qc
    assert isinstance(qc["summary"], list)
    assert qc["domain"] == "general"
    assert "lint_ok" in qc
    assert "size_ok" in qc
    assert "audit_ok" in qc


def test_attach_quality_check_off() -> None:
    result = {
        "skill_folder": {"skill_md": _GOOD_SKILL, "skill_name": "good"},
        "identity_yaml": "name: x\n",
    }
    _attach_quality_check(
        result, run_check=False, check_strict=False, check_domain=""
    )
    assert result["quality_check"] is None
    assert result["_check_options"]["run_check"] is False


def test_attach_quality_check_on() -> None:
    result = {
        "skill_folder": {"skill_md": _GOOD_SKILL, "skill_name": "good"},
        "identity_yaml": "name: x\n",
    }
    _attach_quality_check(
        result, run_check=True, check_strict=False, check_domain="general"
    )
    assert result["quality_check"] is not None
    assert result["quality_check"]["passed"] in (True, False)
    assert result["_check_options"]["run_check"] is True


def test_attach_quality_check_strict_implies_run() -> None:
    result = {
        "skill_folder": {"skill_md": _GOOD_SKILL, "skill_name": "good"},
        "identity_yaml": "name: x\n",
    }
    _attach_quality_check(
        result, run_check=False, check_strict=True, check_domain=""
    )
    assert result["quality_check"] is not None
    assert result["quality_check"]["strict"] is True


def test_attach_quality_check_no_skill() -> None:
    result: dict = {"identity_yaml": "name: x\n"}
    _attach_quality_check(
        result, run_check=True, check_strict=False, check_domain=""
    )
    assert result["quality_check"]["skipped"] is True


def test_refine_returns_quality_check(client_and_job):
    client, job = client_and_job
    # Seed check options so refine re-runs the gate
    job.result["_check_options"] = {
        "run_check": True,
        "check_strict": False,
        "check_domain": "data engineering",
    }
    job.result["_refine_context"]["run_check"] = True
    job.result["_refine_context"]["check_strict"] = False
    job.result["_refine_context"]["check_domain"] = "data engineering"

    resp = client.post(
        f"/api/forge/{job.id}/refine",
        json={"edits": {"methodology": "Always validate schemas before load"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "quality_check" in data
    assert data["quality_check"] is not None
    assert "passed" in data["quality_check"]
    assert data["quality_check"]["domain"] == "data engineering"


@pytest.fixture
def client_and_job():
    """App client + completed job with full refine context."""
    from fastapi.testclient import TestClient

    from tests.test_forge_routes import _make_job_result

    app = create_app()
    store: JobStore = app.state.jobs
    job = store.create()
    job.status = "done"
    job.result = _make_job_result()
    # Use a more complete skill so lint is meaningful
    job.result["skill_folder"]["skill_md"] = _GOOD_SKILL
    return TestClient(app), job
