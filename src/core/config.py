"""
Configuration Management

Loads configuration from YAML and environment variables.
"""
import os
from dotenv import load_dotenv
import yaml
from pathlib import Path
from typing import Any, Dict


class Config:
    """Configuration manager with environment variable interpolation"""

    def __init__(self, config_path: str = "config/app.yaml"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        # Load .env file before loading config
        load_dotenv()
        self.load()

    def load(self):
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            raw_config = yaml.safe_load(f)

        # Interpolate environment variables
        self._config = self._interpolate_env(raw_config)

    def _interpolate_env(self, obj: Any) -> Any:
        """Recursively replace ${VAR} and ${VAR:default} with env values"""
        if isinstance(obj, dict):
            return {k: self._interpolate_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._interpolate_env(item) for item in obj]
        elif isinstance(obj, str):
            if obj.startswith('${') and obj.endswith('}'):
                # Extract variable and optional default
                var_expr = obj[2:-1]
                if ':' in var_expr:
                    var_name, default = var_expr.split(':', 1)
                    return os.getenv(var_name, default)
                else:
                    value = os.getenv(var_expr)
                    if value is None:
                        raise ValueError(f"Environment variable {var_expr} not set and no default provided")
                    return value
        return obj

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-separated key"""
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    def __getitem__(self, key: str) -> Any:
        """Access config via dictionary syntax"""
        return self.get(key)

    @property
    def all(self) -> Dict[str, Any]:
        """Get entire configuration"""
        return self._config


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get global configuration instance"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def load_config(config_path: str = "config/app.yaml"):
    """Load configuration from specific path"""
    global _config
    _config = Config(config_path)
    return _config
