import os

from latency_dashboard.config import load_config


def test_config_prod_json_loads() -> None:
    root = os.path.join(os.path.dirname(__file__), "..", "..", "config", "config.prod.json")
    config = load_config(root)
    assert config.config_version == "v2-llm-configs"
    assert config.provider == "gen-ai-router"
    assert len(config.llm_configs) == 2
    assert config.llm_configs[0].provider == "AZURE_OPEN_AI"
    assert config.llm_configs[0].routerUrl == "??????"
