"""Configuration loader - loads app.yaml and creates all service instances."""

import yaml
import os
from pathlib import Path
from dataclasses import dataclass

from src.models.adapter import ModelConfig, ModelFactory
from src.resilience.circuit_breaker import CircuitConfig
from src.resilience.retry import RetryConfig


@dataclass
class AppConfig:
    model_config_dict: dict
    fallback_model_configs: list[dict]
    embedding_config_dict: dict
    redis_url: str
    circuit_config: CircuitConfig
    retry_config: RetryConfig
    server_host: str
    server_port: int
    prompt_dir: str

    @classmethod
    def load(cls, config_path: str = "config/app.yaml") -> "AppConfig":
        path = Path(config_path)
        if not path.exists():
            # Try relative to this file
            path = Path(__file__).parent.parent / config_path
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        def resolve_env(val):
            if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
                return os.environ.get(val[2:-1], "")
            return val

        model_cfg = dict(data.get("model", {}))
        model_cfg["api_key"] = resolve_env(model_cfg.get("api_key", ""))

        fallback_cfgs = []
        for fc in data.get("fallback_models", []):
            fc = dict(fc)
            fc["api_key"] = resolve_env(fc.get("api_key", ""))
            fallback_cfgs.append(fc)

        embedding_cfg = dict(data.get("embedding", {}))
        embedding_cfg["api_key"] = resolve_env(embedding_cfg.get("api_key", ""))

        cb = data.get("circuit_breaker", {})
        rq = data.get("retry", {})
        srv = data.get("server", {})

        return cls(
            model_config_dict=model_cfg,
            fallback_model_configs=fallback_cfgs,
            embedding_config_dict=embedding_cfg,
            redis_url=data.get("redis", {}).get("url", "redis://localhost:6379/0"),
            circuit_config=CircuitConfig(
                failure_threshold=cb.get("failure_threshold", 5),
                failure_rate_threshold=cb.get("failure_rate_threshold", 0.5),
                recovery_timeout=cb.get("recovery_timeout", 30),
                min_requests=cb.get("min_requests", 10),
            ),
            retry_config=RetryConfig(
                max_retries=rq.get("max_retries", 3),
                base_delay=rq.get("base_delay", 1.0),
                max_delay=rq.get("max_delay", 30.0),
            ),
            server_host=srv.get("host", "0.0.0.0"),
            server_port=srv.get("port", 8000),
            prompt_dir=str(Path(__file__).parent.parent / "prompts"),
        )
