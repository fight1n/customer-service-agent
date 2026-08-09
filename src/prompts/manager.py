"""D6 Layer 1 - Prompt template manager.

Loads prompt templates from YAML files, supports variable injection,
and provides version management via filename conventions (name_vN.yaml).
"""

import yaml
from pathlib import Path


class PromptManager:
    """Manages prompt templates loaded from YAML files."""

    def __init__(self, prompt_dir: str = "prompts"):
        self.prompt_dir = Path(prompt_dir)
        self._cache: dict[str, str] = {}

    def load(self, name: str, version: str = "latest") -> str:
        """Load a raw prompt template by name and version.

        Files should be named: {name}_v{N}.yaml
        """
        cache_key = f"{name}:{version}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if version == "latest":
            files = sorted(self.prompt_dir.glob(f"{name}_v*.yaml"))
            if not files:
                raise FileNotFoundError(
                    f"No prompt template found for '{name}' in {self.prompt_dir}"
                )
            filepath = files[-1]
        else:
            filepath = self.prompt_dir / f"{name}_v{version}.yaml"

        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            template = data["template"]

        self._cache[cache_key] = template
        return template

    def render(self, name: str, variables: dict, version: str = "latest") -> str:
        """Load a template and inject variables via str.format()."""
        template = self.load(name, version)
        return template.format(**variables)

    def clear_cache(self):
        self._cache.clear()
