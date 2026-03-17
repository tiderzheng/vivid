import json

from app.subsystems.vision import load_vision_store
from app.subsystems.vision.models import VisionApiConfig, VisionPromptItem
from app.subsystems.vision.store import save_vision_store


def test_load_vision_store(tmp_path):
    api_configs_path = tmp_path / "api_configs.json"
    prompts_path = tmp_path / "prompts.json"
    api_configs_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "cfg-1",
                        "name": "cfg",
                        "api_base": "http://localhost:1234",
                        "api_path": "/v1/chat/completions",
                        "model": "model-x",
                        "timeout": 15,
                        "prompt": "prompt-x",
                        "system_prompt": "sys-x",
                        "api_key_env": "OCR_API_KEY",
                    }
                ],
                "selected_id": "cfg-1",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    prompts_path.write_text(
        json.dumps(
            [
                {"id": "default", "name": "默认", "content": "只返回字幕"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    store = load_vision_store(api_configs_path, prompts_path)
    assert store.selected_api_config_id == "cfg-1"
    assert store.get_api_config(None) is not None
    assert store.get_prompt("default") is not None


def test_save_and_select_vision_store(tmp_path):
    api_configs_path = tmp_path / "api_configs.json"
    prompts_path = tmp_path / "prompts.json"
    store = load_vision_store(api_configs_path, prompts_path)
    store.upsert_api_config(
        VisionApiConfig(
            id="cfg-2",
            name="cfg2",
            api_base="http://localhost:1234",
            model="model-y",
        )
    )
    store.upsert_prompt(
        VisionPromptItem(
            id="strict",
            name="严格",
            content="只返回字幕",
        )
    )
    assert store.select_api_config("cfg-2") is True
    save_vision_store(store, api_configs_path, prompts_path)
    reloaded = load_vision_store(api_configs_path, prompts_path)
    assert reloaded.selected_api_config_id == "cfg-2"
    assert reloaded.get_prompt("strict") is not None
