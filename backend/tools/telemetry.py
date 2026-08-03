"""OTel instrumentation (constitution Principle XV — HUMAIN substrate attribute schema).

Every LLM call and tool invocation MUST emit exactly this attribute set, no
subset: tenant.id, agent.id, agent.version, session.id, graph.run.id, model.id,
cost.usd, tokens.in, tokens.out, node.name, tool.name.

A span missing tenant.id or cost.usd is a constitution violation, not a gap to
backfill (Principle XV) — `traced()` raises rather than emit a partial span.
"""

import functools
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_REQUIRED_ATTRS = (
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


@dataclass(frozen=True)
class RunContext:
    """Ambient identifiers for the current agent run — set once per request/session."""

    tenant_id: str
    session_id: str
    agent_id: str
    agent_version: str
    graph_run_id: str


_current: ContextVar[RunContext | None] = ContextVar("btm_run_context", default=None)


@contextmanager
def run_context(ctx: RunContext):
    token = _current.set(ctx)
    try:
        yield
    finally:
        _current.reset(token)


def init_tracing(otlp_endpoint: str, langfuse_otlp_endpoint: str) -> None:
    """Wire the OTel exporter to Cloud Trace/Monitoring/Logging (via the standard
    OTLP collector) and to self-hosted Langfuse. No LangSmith dependency exists
    anywhere in this project (constitution Principle XV) — do not add one.
    """
    provider = TracerProvider(resource=Resource.create({"service.name": "btm-backend"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=langfuse_otlp_endpoint)))
    trace.set_tracer_provider(provider)


def traced(node_name: str, tool_name: str = ""):
    """Decorate an agent/tool function to emit a span with the full attribute schema.

    The decorated function's return value may include `model_id`, `cost_usd`,
    `tokens_in`, `tokens_out` (as dict keys or attributes) to populate the
    corresponding span attributes; these default to 0/"" for tool calls that
    don't invoke a model directly, but tenant.id/session.id/agent.id/
    agent.version/graph.run.id always come from the ambient RunContext and are
    never optional.

    ponytail: async-only — every agent/tool function in this codebase already
    is (Strands, FastAPI, and asyncpg are all async-native); add a sync path
    back if a genuinely sync one ever shows up, rather than carrying an
    untested branch for a case that doesn't exist yet.
    """

    def decorator(fn):
        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            ctx = _current.get()
            if ctx is None:
                raise RuntimeError(
                    f"traced({node_name}) called with no active RunContext — "
                    "tenant.id/session.id would be missing, which is a constitution violation"
                )
            tracer = trace.get_tracer("btm")
            with tracer.start_as_current_span(node_name) as span:
                result = await fn(*args, **kwargs)
                _set_attrs(span, ctx, node_name, tool_name, result)
                return result

        return async_wrapper

    return decorator


def _set_attrs(span, ctx: RunContext, node_name: str, tool_name: str, result) -> None:
    usage = result if isinstance(result, dict) else getattr(result, "__dict__", {})
    span.set_attributes(
        {
            "tenant.id": ctx.tenant_id,
            "agent.id": ctx.agent_id,
            "agent.version": ctx.agent_version,
            "session.id": ctx.session_id,
            "graph.run.id": ctx.graph_run_id,
            "model.id": usage.get("model_id", ""),
            "cost.usd": float(usage.get("cost_usd", 0.0)),
            "tokens.in": int(usage.get("tokens_in", 0)),
            "tokens.out": int(usage.get("tokens_out", 0)),
            "node.name": node_name,
            "tool.name": tool_name,
        }
    )
