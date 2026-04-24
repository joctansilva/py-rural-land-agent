from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "fazendas"
    postgres_user: str = "postgres"
    postgres_password: str

    openai_api_key: str = ""
    # aceita tanto ANTHROPIC_API_KEY quanto CLAUDE_API_KEY
    anthropic_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("anthropic_api_key", "claude_api_key"),
    )
    google_api_key: str = ""

    agent_model: str = ""
    agent_max_tokens: int = 1024
    debug: bool = False

    @model_validator(mode="after")
    def check_llm_api_key(self) -> "Settings":
        if not any([self.openai_api_key, self.anthropic_api_key, self.google_api_key]):
            raise ValueError(
                "Configure ao menos uma chave: OPENAI_API_KEY, ANTHROPIC_API_KEY ou GOOGLE_API_KEY"
            )
        return self

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()