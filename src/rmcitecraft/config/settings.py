"""Application settings and configuration management."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM Settings
    default_llm_provider: str = Field(default="anthropic", description="Default LLM provider")
    llm_temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    llm_max_tokens: int = Field(default=1024, ge=100, le=4096)

    # API Keys
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")
    anthropic_model: str = Field(default="claude-3-5-sonnet-20241022")
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o-mini")
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.1:8b")

    # Database Paths
    rm_database_path: str = Field(
        default="data/Iiams.rmtree",
        description="Path to RootsMagic .rmtree file",
    )
    sqlite_icu_extension: str = Field(
        default="./sqlite-extension/icu.dylib",
        description="Path to ICU extension for RMNOCASE collation",
    )
    rm_media_root_directory: str = Field(
        default="/Users/miams/Genealogy/RootsMagic/Files/Records - Census",
        description="RootsMagic media folder (replaces ? in paths)",
    )

    # Output Settings
    output_dir: str = Field(default="output", description="Output directory")
    export_dir: str = Field(default="exports", description="Export directory")

    # Download Monitoring
    download_folder: str = Field(
        default="~/Downloads",
        description="Folder to monitor for census image downloads",
    )
    download_timeout_minutes: int = Field(default=15, ge=1, le=60)

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="logs/rmcitecraft.log", description="Main log file")
    llm_debug_log_file: str = Field(
        default="logs/llm_debug.jsonl",
        description="LLM request/response debug log",
    )

    # Application Settings
    enable_prompt_caching: bool = Field(default=True, description="Enable LLM prompt caching")
    batch_size: int = Field(default=10, ge=1, le=100, description="Batch processing size")
    preview_before_save: bool = Field(
        default=True,
        description="Show preview before saving to database",
    )

    @field_validator("rm_database_path", "sqlite_icu_extension")
    @classmethod
    def validate_path_exists(cls, v: str) -> str:
        """Validate that file paths exist."""
        path = Path(v)
        if not path.exists():
            # Don't fail hard - just warn. File might be created later.
            pass
        return str(path)

    @field_validator("download_folder", "rm_media_root_directory")
    @classmethod
    def expand_user_path(cls, v: str) -> str:
        """Expand user home directory in paths."""
        return str(Path(v).expanduser())


# Global configuration instance
_config: Config | None = None


def get_config() -> Config:
    """Get or create the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
