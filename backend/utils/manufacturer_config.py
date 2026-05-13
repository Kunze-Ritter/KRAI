"""
Manufacturer Configuration Loader

Loads manufacturer-specific configurations (patterns, series, parts) from YAML files.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ManufacturerConfig:
    """Manufacturer configuration"""

    canonical_name: str
    aliases: list[str]
    product_patterns: list[dict[str, Any]]
    series: list[dict[str, Any]]
    part_prefixes: list[dict[str, Any]]
    reject_patterns: list[dict[str, Any]]

    def get_compiled_patterns(self) -> list[tuple]:
        """Get compiled regex patterns for product extraction"""
        compiled = []
        for pattern_def in self.product_patterns:
            pattern_str = pattern_def["pattern"]
            flags = re.IGNORECASE if pattern_def.get("flags") == "IGNORECASE" else 0
            compiled_pattern = re.compile(pattern_str, flags)
            compiled.append(
                (pattern_def.get("series", "Unknown"), compiled_pattern, pattern_def.get("type", "laser_multifunction"))
            )
        return compiled

    def get_reject_patterns(self) -> list[re.Pattern]:
        """Get compiled reject patterns"""
        compiled = []
        for reject_def in self.reject_patterns:
            pattern_str = reject_def["pattern"]
            compiled.append(re.compile(pattern_str, re.IGNORECASE))
        return compiled


class ManufacturerConfigLoader:
    """Load manufacturer configurations from YAML files"""

    def __init__(self, config_dir: Path | None = None):
        """
        Initialize config loader

        Args:
            config_dir: Directory containing manufacturer YAML configs
                       Default: backend/configs/
        """
        if config_dir is None:
            # Default to backend/configs/
            backend_dir = Path(__file__).parent.parent
            config_dir = backend_dir / "configs"

        self.config_dir = Path(config_dir)
        self._cache: dict[str, ManufacturerConfig] = {}

    def load_config(self, manufacturer: str) -> ManufacturerConfig | None:
        """
        Load configuration for a manufacturer

        Args:
            manufacturer: Manufacturer name (e.g., "Lexmark", "Konica Minolta", "HP")

        Returns:
            ManufacturerConfig or None if not found
        """
        # Normalize manufacturer name for filename
        manufacturer_key = manufacturer.lower().replace(" ", "_").replace("-", "_")

        # Check cache
        if manufacturer_key in self._cache:
            return self._cache[manufacturer_key]

        # Try to load from file
        config_file = self.config_dir / f"{manufacturer_key}.yaml"

        if not config_file.exists():
            # Try alternative names
            alternatives = [
                "hp_inc",  # HP Inc. -> hp_inc
                "hewlett_packard",  # Hewlett Packard -> hewlett_packard
            ]

            for alt in alternatives:
                alt_file = self.config_dir / f"{alt}.yaml"
                if alt_file.exists():
                    config_file = alt_file
                    break
            else:
                return None

        try:
            with open(config_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            config = ManufacturerConfig(
                canonical_name=data["manufacturer"]["canonical_name"],
                aliases=data["manufacturer"]["aliases"],
                product_patterns=data.get("product_patterns", []),
                series=data.get("series", []),
                part_prefixes=data.get("part_prefixes", []),
                reject_patterns=data.get("reject_patterns", []),
            )

            # Cache it
            self._cache[manufacturer_key] = config

            return config

        except Exception as e:
            print(f"Error loading config for {manufacturer}: {e}")
            return None

    def list_available_configs(self) -> list[str]:
        """List all available manufacturer configs"""
        configs = []
        for yaml_file in self.config_dir.glob("*.yaml"):
            # Convert filename to manufacturer name
            name = yaml_file.stem.replace("_", " ").title()
            configs.append(name)
        return sorted(configs)


# Global loader instance
_loader = ManufacturerConfigLoader()


def get_manufacturer_config(manufacturer: str) -> ManufacturerConfig | None:
    """
    Get configuration for a manufacturer

    Args:
        manufacturer: Manufacturer name

    Returns:
        ManufacturerConfig or None
    """
    return _loader.load_config(manufacturer)


def list_available_manufacturers() -> list[str]:
    """List all manufacturers with configs"""
    return _loader.list_available_configs()


if __name__ == "__main__":
    # Test
    print("Available Manufacturers:")
    for mfr in list_available_manufacturers():
        print(f"  - {mfr}")

    print("\nTesting Lexmark config:")
    config = get_manufacturer_config("Lexmark")
    if config:
        print(f"  Canonical Name: {config.canonical_name}")
        print(f"  Aliases: {config.aliases}")
        print(f"  Product Patterns: {len(config.product_patterns)}")
        print(f"  Series: {len(config.series)}")
        print(f"  Part Prefixes: {len(config.part_prefixes)}")

    print("\nTesting Konica Minolta config:")
    config = get_manufacturer_config("Konica Minolta")
    if config:
        print(f"  Canonical Name: {config.canonical_name}")
        print(f"  Product Patterns: {len(config.product_patterns)}")
        print(f"  Series: {len(config.series)}")
