from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.core.auth_service import AuthMiddleware
from app.core.reporting.aggregator import ReportData, ExecutionSummary, NodeResult
from app.core.reporting.generator import ReportGenerator
from app.domains.auth.schemas import AuthTypeEnum


class FakeRedis:
    def __init__(self):
        self.data = {}
        self.ttl = None

    async def hset(self, key, mapping):
        self.data.setdefault(key, {}).update(mapping)

    async def hgetall(self, key):
        return dict(self.data.get(key, {}))

    async def expire(self, key, ttl):
        self.ttl = (key, ttl)


@pytest.mark.asyncio
async def test_auth_cache_reads_and_writes_via_redis_hash():
    middleware = AuthMiddleware(Mock())
    middleware._redis_client = FakeRedis()

    auth_config = SimpleNamespace(project_id=1, static_value="token-123", auth_type=AuthTypeEnum.BEARER.value)
    result = await middleware._handle_static_mode(auth_config)

    assert result["success"] is True
    cached = await middleware._get_auth_variables(1)
    assert cached["ACCESS_TOKEN"] == "token-123"
    assert middleware._redis_client.ttl is not None


@pytest.mark.asyncio
async def test_pdf_generator_falls_back_to_valid_pdf_bytes():
    report_data = ReportData(
        summary=ExecutionSummary(
            scenario_id=1,
            scenario_name="Checkout",
            environment_id=2,
            environment_name="test",
            status="completed",
            total_nodes=1,
            passed_nodes=1,
            failed_nodes=0,
            skipped_nodes=0,
            total_duration_ms=12,
            started_at=datetime.now(timezone.utc),
        ),
        node_results=[
            NodeResult(
                node_key="create_order",
                node_name="Create Order",
                node_type="api_call",
                status="passed",
                response_time=12,
                response_code=200,
            )
        ],
    )

    generator = ReportGenerator()
    with patch.object(generator, "_render_pdf_via_playwright", side_effect=RuntimeError("no browser")):
        pdf_bytes = await generator.generate_pdf_report(report_data, include_rca=False)

    assert pdf_bytes.startswith(b"%PDF")
