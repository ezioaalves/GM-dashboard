"""Contract checks that do not require a running PostgreSQL instance."""
import os

os.environ.setdefault("DATABASE_URL", "postgresql://kaihou_gm:kaihou_gm_dev@127.0.0.1:54329/kaihou_gm")

from gm_dashboard.api import app


def test_campaign_workflow_routes_are_exposed():
    paths = app.openapi()["paths"]
    expected = {
        "/api/arcs", "/api/arcs/{arc_id}/activate", "/api/arcs/{arc_id}/links",
        "/api/ideas", "/api/ideas/{idea_id}/promote", "/api/truths",
        "/api/truths/{truth_id}/supersede", "/api/creative-proposals",
        "/api/creative-proposals/{proposal_id}/decision",
        "/api/creative-proposals/{proposal_id}/apply", "/api/context-packets",
    }
    assert expected <= paths.keys()


def test_context_packet_requires_task_in_json_or_query_contract():
    operation = app.openapi()["paths"]["/api/context-packets"]["post"]
    schema = operation["requestBody"]["content"]["application/json"]["schema"]
    refs = [item.get("$ref", "") for item in schema.get("anyOf", [schema])]
    assert any("ContextPacketIn" in ref for ref in refs)
