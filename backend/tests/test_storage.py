from latency_dashboard.config import get_llm_config_label, get_source_label, load_config


def test_get_llm_config_label_falls_back_when_id_not_in_config() -> None:
    config = load_config(
        str(
            __import__("pathlib").Path(__file__).resolve().parents[2]
            / "config"
            / "config.prod.json"
        )
    )
    assert get_llm_config_label(config, "unknown-id") == "unknown-id"


def test_get_source_label_returns_source_region_id() -> None:
    config = load_config(
        str(
            __import__("pathlib").Path(__file__).resolve().parents[2]
            / "config"
            / "config.prod.json"
        )
    )
    assert get_source_label(config, "eastus") == "eastus"
