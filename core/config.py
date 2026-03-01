"""
Configuration loader for Jarvis
"""
import os
import re
import toml
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


def _resolve_env_vars(value: Any) -> Any:
    """
    Resolve environment variable placeholders in a value.
    Supports ${VAR} and ${VAR:default} syntax.
    """
    if not isinstance(value, str):
        return value
    
    # Match ${VAR} or ${VAR:default}
    pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
    
    def replacer(match):
        var_name = match.group(1)
        default = match.group(2)
        env_value = os.environ.get(var_name, default if default is not None else "")
        return env_value
    
    return re.sub(pattern, replacer, value)


def _resolve_config_values(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively resolve env vars in config dictionary."""
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = _resolve_config_values(value)
        elif isinstance(value, list):
            result[key] = [_resolve_env_vars(item) for item in value]
        else:
            result[key] = _resolve_env_vars(value)
    return result


@dataclass
class VoiceConfig:
    """Voice service configuration"""
    stt_model: str = "base"
    tts_engine: str = "pyttsx3"
    sample_rate: int = 16000
    hotkey: str = "ctrl+alt+j"


@dataclass
class MemoryConfig:
    """Memory service configuration"""
    db_type: str = "sqlite"
    vector_db: str = "chroma"
    chroma_persist_directory: str = "./data/chroma"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "jarvis"
    postgres_user: str = "jarvis"
    postgres_password: str = ""


@dataclass
class LLMConfig:
    """LLM configuration"""
    provider: str = "openai"
    model: str = "gpt-4"
    api_key: str = ""
    base_url: str = "http://localhost:11434"
    temperature: float = 0.7
    max_tokens: int = 4000
    tools_enabled: bool = True


@dataclass
class OSOperatorConfig:
    """OS Operator configuration"""
    screenshot_dir: str = "./data/screenshots"
    default_delay: float = 0.1
    safety_confirm_destructive: bool = True


@dataclass
class SafetyConfig:
    """Safety configuration"""
    require_confirmation_for_destructive: bool = True
    allowed_apps: list = field(default_factory=lambda: ["chrome", "firefox", "vscode", "notepad", "explorer"])
    blocked_actions: list = field(default_factory=lambda: ["delete_files", "format_drive", "send_email"])


@dataclass
class AppConfig:
    """Main application configuration"""
    name: str = "Jarvis"
    version: str = "0.1.0"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    os_operator: OSOperatorConfig = field(default_factory=OSOperatorConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)


_config: Optional[AppConfig] = None


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load configuration from TOML file"""
    global _config
    
    if _config is not None:
        return _config
    
    if config_path is None:
        config_path = os.environ.get("JARVIS_CONFIG", "config/settings.toml")
    
    config_file = Path(config_path)
    
    if not config_file.exists():
        # Return default config
        _config = AppConfig()
        return _config
    
    with open(config_file, "r") as f:
        data = toml.load(f)
    
    # Resolve environment variables in config
    data = _resolve_config_values(data)
    
    app_data = data.get("app", {})
    voice_data = data.get("voice", {})
    memory_data = data.get("memory", {})
    llm_data = data.get("llm", {})
    os_data = data.get("os_operator", {})
    safety_data = data.get("safety", {})
    
    _config = AppConfig(
        name=app_data.get("name", "Jarvis"),
        version=app_data.get("version", "0.1.0"),
        debug=app_data.get("debug", True),
        host=app_data.get("host", "0.0.0.0"),
        port=app_data.get("port", 8000),
        voice=VoiceConfig(**voice_data),
        memory=MemoryConfig(**memory_data),
        llm=LLMConfig(**llm_data),
        os_operator=OSOperatorConfig(**os_data),
        safety=SafetyConfig(**safety_data),
    )
    
    return _config


def get_config() -> AppConfig:
    """Get current configuration"""
    global _config
    if _config is None:
        return load_config()
    return _config
