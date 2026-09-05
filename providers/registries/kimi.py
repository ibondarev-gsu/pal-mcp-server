"""Registry loader for Moonshot Kimi model capabilities."""

from __future__ import annotations

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class KimiModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/kimi_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="KIMI_MODELS_CONFIG_PATH",
            default_filename="kimi_models.json",
            provider=ProviderType.KIMI,
            friendly_prefix="Kimi ({model})",
            config_path=config_path,
        )
