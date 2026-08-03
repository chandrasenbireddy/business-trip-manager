"""Unit test for tools/telemetry.py's @traced decorator (constitution
Principle XV — the full 11-field attribute schema, no subset).

Written during Polish (T108/T110) after a real coverage run showed the
no-RunContext safety check itself was never exercised.
"""

import pytest

from tools.telemetry import RunContext, _current, run_context, traced

REQUIRED_ATTRS = (
    "tenant.id",
    "agent.id",
    "agent.version",
    "session.id",
    "graph.run.id",
    "model.id",
    "cost.usd",
    "tokens.in",
    "tokens.out",
    "node.name",
    "tool.name",
)


@pytest.mark.asyncio
async def test_traced_raises_without_an_active_run_context():
    @traced("test.node")
    async def fn():
        return {}

    # conftest.py's autouse _ambient_run_context fixture always has one set —
    # clear it here to exercise the actual "forgot to establish a context" case.
    token = _current.set(None)
    try:
        with pytest.raises(RuntimeError, match="no active RunContext"):
            await fn()
    finally:
        _current.reset(token)


@pytest.mark.asyncio
async def test_traced_span_carries_the_full_attribute_schema_no_subset():
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    @traced("test.node", tool_name="test_tool")
    async def fn():
        return {"model_id": "deepseek-v3.2", "cost_usd": 0.01, "tokens_in": 10, "tokens_out": 5}

    with run_context(RunContext(tenant_id="t1", session_id="s1", agent_id="a1", agent_version="0.1.0", graph_run_id="g1")):
        await fn()

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    attrs = spans[0].attributes
    for attr_name in REQUIRED_ATTRS:
        assert attr_name in attrs, f"missing required attribute: {attr_name}"
    assert attrs["tenant.id"] == "t1"
    assert attrs["cost.usd"] == 0.01
    assert attrs["tool.name"] == "test_tool"
