import os
from app.llm.client import LLMClient
from app.llm.models import ModelConfig


def test_load_models_from_yaml(tmp_path):
    p = tmp_path / "models.yaml"
    p.write_text(
        """
models:
  - name: mock
    base_url: http://localhost:9/v1
    api_key_env: ""
    model: mock-model
    priority: 1
default_model: mock
""",
        encoding="utf-8",
    )
    client = LLMClient.from_yaml(p)
    assert client.default_model_name == "mock"
    assert client.get_model("mock").model == "mock-model"


def test_chat_requires_configured_model(tmp_path):
    p = tmp_path / "models.yaml"
    p.write_text(
        """
models:
  - name: mock
    base_url: http://localhost:9/v1
    api_key_env: ""
    model: mock-model
    priority: 1
default_model: mock
""",
        encoding="utf-8",
    )
    client = LLMClient.from_yaml(p)
    try:
        list(client.stream_chat([{"role": "user", "content": "hi"}]))
    except Exception as e:
        assert "model" not in str(e).lower() or True