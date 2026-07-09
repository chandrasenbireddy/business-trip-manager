"""agents/orchestrator._extract_trip_details: strands.Agent never actually had
an extract_structured method — every real call raised AttributeError. Fixed
by calling NVIDIA NIM (orchestrator's primary provider) directly via the
OpenAI-compatible chat completions API, with Groq as call_with_fallback's
retry target — same pattern both providers already implement.

No prior test exercised this function's real logic at all: every
integration test patches agents.orchestrator._extract_trip_details away
entirely (it was an unusable stub before this fix).
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.orchestrator import _extract_trip_details, _parse_extraction


def _fake_response(content: str):
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


DETAILS_JSON = json.dumps(
    {
        "destination": "Riyadh",
        "start_date": "2026-07-14",
        "end_date": "2026-07-17",
        "purpose": "HUMAIN kickoff",
        "budget": 1500,
        "reference_point": "KAFD",
        "origin": None,
    }
)


@pytest.mark.asyncio
async def test_extract_trip_details_calls_nvidia_primary_and_parses_the_response():
    mock_create = AsyncMock(return_value=_fake_response(DETAILS_JSON))
    with patch("agents.orchestrator.AsyncOpenAI") as mock_openai_cls:
        mock_openai_cls.return_value.chat.completions.create = mock_create
        result = await _extract_trip_details("I need to go to Riyadh July 14-17 for the HUMAIN kickoff, budget $1500, near KAFD")

    assert result["destination"] == "Riyadh"
    assert result["start_date"] == "2026-07-14"
    assert result["budget"] == 1500
    assert result["reference_point"] == "KAFD"
    assert result["origin"] is None

    call_kwargs = mock_create.await_args.kwargs
    assert call_kwargs["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
    assert call_kwargs["response_format"] == {"type": "json_object"}
    client_kwargs = mock_openai_cls.call_args.kwargs
    assert client_kwargs["base_url"] == "https://integrate.api.nvidia.com/v1"


@pytest.mark.asyncio
async def test_extract_trip_details_falls_back_to_groq_on_primary_failure():
    mock_create = AsyncMock(side_effect=[Exception("NIM rate limited"), _fake_response(DETAILS_JSON)])
    with patch("agents.orchestrator.AsyncOpenAI") as mock_openai_cls:
        mock_openai_cls.return_value.chat.completions.create = mock_create
        result = await _extract_trip_details("some trip request")

    assert result["destination"] == "Riyadh"
    assert mock_create.await_count == 2
    # Second AsyncOpenAI(...) construction must point at Groq, not NVIDIA again.
    second_client_kwargs = mock_openai_cls.call_args_list[1].kwargs
    assert second_client_kwargs["base_url"] == "https://api.groq.com/openai/v1"
    second_call_kwargs = mock_create.await_args_list[1].kwargs
    assert second_call_kwargs["model"] == "llama-3.3-70b-versatile"


def test_parse_extraction_strips_a_markdown_json_fence():
    fenced = f"```json\n{DETAILS_JSON}\n```"
    result = _parse_extraction(fenced)
    assert result["destination"] == "Riyadh"


def test_parse_extraction_drops_unrequested_fields_and_defaults_missing_ones():
    result = _parse_extraction(json.dumps({"destination": "Jeddah", "unexpected_field": "ignored"}))
    assert result["destination"] == "Jeddah"
    assert "unexpected_field" not in result
    assert result["start_date"] is None


def test_parse_extraction_raises_on_malformed_json():
    with pytest.raises(json.JSONDecodeError):
        _parse_extraction("not json at all")
