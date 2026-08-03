"""LLM client usage accumulation + telemetry emit."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from agentforge.llm.client import LLMClient
from agentforge.telemetry import reset_sink_for_tests
from agentforge.telemetry.sink import TelemetrySink


def test_record_usage_anthropic_shape(tmp_path) -> None:
    sink = TelemetrySink(mode="local", directory=tmp_path)
    reset_sink_for_tests(sink)
    client = LLMClient(api_key="sk-ant-test", provider="anthropic")
    response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=100, output_tokens=40),
    )
    client._record_usage(response)
    assert client.usage["prompt_tokens"] == 100
    assert client.usage["completion_tokens"] == 40
    assert client.usage["total_tokens"] == 140
    assert client.usage["calls"] == 1
    assert sink.path is not None
    text = sink.path.read_text()
    assert "llm_usage" in text
    assert "100" in text


def test_record_usage_openai_shape(tmp_path) -> None:
    reset_sink_for_tests(TelemetrySink(mode="off", directory=tmp_path))
    client = LLMClient(api_key="sk-test", provider="openai")
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )
    client._record_usage(response)
    assert client.usage["total_tokens"] == 15


def test_record_usage_missing_usage_still_counts_call() -> None:
    client = LLMClient(api_key="sk-ant-test", provider="anthropic")
    client._record_usage(SimpleNamespace())
    assert client.usage["calls"] == 1
    assert client.usage["total_tokens"] == 0


def test_anthropic_retry_path_records_usage() -> None:
    client = LLMClient(api_key="sk-ant-test", provider="anthropic")
    mock_resp = MagicMock()
    mock_resp.usage = SimpleNamespace(input_tokens=7, output_tokens=3)
    client._anthropic_client = MagicMock()
    client._anthropic_client.messages.create.return_value = mock_resp
    out = client._call_anthropic_with_retry(model="x", messages=[], max_tokens=10)
    assert out is mock_resp
    assert client.usage["prompt_tokens"] == 7
