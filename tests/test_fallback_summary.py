import requests

from app.adapters.llm import LlmAdapter, fallback_summary
from app.exceptions import VividError
from app.subsystems.summary.models import SummaryProviderConfig
from app.utils.json_utils import extract_json_block


def test_fallback_summary_provider():
    result = fallback_summary("hello world")
    assert result.provider == "rule-based fallback"


def test_extract_json_block_raises_vividerror_on_invalid_json():
    try:
        extract_json_block("not-json")
    except VividError as exc:
        assert "valid JSON" in str(exc)
    else:
        raise AssertionError("invalid JSON should raise VividError")


def test_llm_adapter_falls_back_when_provider_returns_invalid_json(monkeypatch):
    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "```json\n{bad json}\n```"}}]}

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: DummyResponse())

    adapter = LlmAdapter(
        providers=[
            SummaryProviderConfig(
                provider_id="provider-a",
                provider_name="Provider A",
                base_url="https://example.com/sf",
                model="model-a",
                api_key="sk-demo",
            )
        ],
        llm_max_chars=2000,
        summary_system_prompt="system-demo",
        summary_user_prompt="请总结以下内容：\n{transcript}",
    )

    result = adapter.summarize("第一句。第二句。第三句。")

    assert result.provider == "rule-based fallback"
    assert result.title
    assert result.overview
    assert result.core_points
    assert result.controversies
    assert result.action_suggestions
    assert result.playful_comment
    assert result.one_line == result.title


def test_llm_adapter_uses_custom_summary_prompt(monkeypatch):
    captured = {}

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"title":"一句话标题",'
                                '"overview":"内容概览",'
                                '"core_points":["观点1","观点2","观点3"],'
                                '"controversies":["争议1"],'
                                '"action_suggestions":["建议1","建议2","建议3"],'
                                '"playful_comment":"俏皮点评"}'
                            )
                        }
                    }
                ]
            }

    def fake_post(*args, **kwargs):
        captured["messages"] = kwargs["json"]["messages"]
        return DummyResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    adapter = LlmAdapter(
        providers=[
            SummaryProviderConfig(
                provider_id="provider-a",
                provider_name="Provider A",
                base_url="https://example.com/sf",
                model="model-a",
                api_key="sk-demo",
            )
        ],
        llm_max_chars=2000,
        summary_system_prompt="custom-system",
        summary_user_prompt="请用中文总结：\n{transcript}",
    )

    result = adapter.summarize("这里是逐字稿。")

    assert result.provider == "Provider A model-a"
    assert captured["messages"][0]["content"] == "custom-system"
    assert captured["messages"][1]["content"] == "请用中文总结：\n这里是逐字稿。"
    assert result.title == "一句话标题"
    assert result.overview == "内容概览"
    assert result.core_points == ["观点1", "观点2", "观点3"]
    assert result.controversies == ["争议1"]
    assert result.action_suggestions == ["建议1", "建议2", "建议3"]
    assert result.playful_comment == "俏皮点评"


def test_llm_adapter_uses_second_openai_compatible_provider_after_first_failure(monkeypatch):
    calls = []

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"title":"一句话标题",'
                                '"overview":"内容概览",'
                                '"core_points":["观点1","观点2","观点3"],'
                                '"controversies":["争议1"],'
                                '"action_suggestions":["建议1","建议2","建议3"],'
                                '"playful_comment":"俏皮点评"}'
                            )
                        }
                    }
                ]
            }

    def fake_post(url, **kwargs):
        calls.append((url, kwargs["headers"]["Authorization"]))
        if len(calls) == 1:
            raise requests.RequestException("provider-a failed")
        return DummyResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    adapter = LlmAdapter(
        providers=[
            SummaryProviderConfig(
                provider_id="provider-a",
                provider_name="Provider A",
                base_url="https://example.com/a",
                model="model-a",
                api_key="sk-a",
            ),
            SummaryProviderConfig(
                provider_id="provider-b",
                provider_name="Provider B",
                base_url="https://example.com/b",
                model="model-b",
                api_key="sk-b",
            ),
        ],
        llm_max_chars=2000,
        summary_system_prompt="custom-system",
        summary_user_prompt="请用中文总结：\n{transcript}",
    )

    result = adapter.summarize("这里是逐字稿。")

    assert calls == [
        ("https://example.com/a", "Bearer sk-a"),
        ("https://example.com/b", "Bearer sk-b"),
    ]
    assert result.provider == "Provider B model-b"
