from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime config, loaded from environment / .env.

    Kept as one flat settings object so every module reads config the same
    way instead of each agent parsing its own env vars.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_generation_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"

    pinecone_api_key: str = ""
    pinecone_index_name: str = "martech-brochures"
    pinecone_embedding_dim: int = 3072

    content_library_db_path: str = "data/content_library.db"
    asset_bank_path: str = "data/assets"
    project_data_path: str = "data/projects"
    api_public_base_url: str = "http://127.0.0.1:8123"
    usage_db_path: str = "data/usage.db"

    # A Gmail *App Password* (Google Account -> Security -> App Passwords),
    # never the account's real login password -- lets the app authenticate
    # as this address over SMTP so a sent email genuinely comes from it and
    # lands in its own Sent folder.
    gmail_address: str = ""
    gmail_app_password: str = ""

    context_top_k: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
