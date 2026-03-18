import requests

from app.adapters.llm import LlmAdapter, fallback_summary
from app.exceptions import VividError
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
        siliconflow_api_key="sk-demo",
        dashscope_api_key=None,
        siliconflow_base_url="https://example.com/sf",
        dashscope_base_url="https://example.com/ds",
        siliconflow_model="model-a",
        dashscope_model="model-b",
        llm_max_chars=2000,
        summary_system_prompt="system-demo",
        summary_user_prompt="请总结以下内容：\n{transcript}",
    )

    result = adapter.summarize("第一句。第二句。第三句。")

    assert result.provider == "rule-based fallback"
    assert result.one_line


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
                            "content": '{"one_line":"一句话","detailed_summary":"详细总结","key_points":["a","b","c"]}'
                        }
                    }
                ]
            }

    def fake_post(*args, **kwargs):
        captured["messages"] = kwargs["json"]["messages"]
        return DummyResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    adapter = LlmAdapter(
        siliconflow_api_key="sk-demo",
        dashscope_api_key=None,
        siliconflow_base_url="https://example.com/sf",
        dashscope_base_url="https://example.com/ds",
        siliconflow_model="model-a",
        dashscope_model="model-b",
        llm_max_chars=2000,
        summary_system_prompt="custom-system",
        summary_user_prompt="请用中文总结：\n{transcript}",
    )

    result = adapter.summarize("这里是逐字稿。")

    assert result.provider == "SiliconFlow model-a"
    assert captured["messages"][0]["content"] == "custom-system"
    assert captured["messages"][1]["content"] == "请用中文总结：\n这里是逐字稿。"
