from pathlib import Path

from dhara_shared.core.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    # --- App ---
    APP_NAME: str = "rag_service"
    APP_VERSION: str = "2.0.0"
    PORT: int = 8007
    HOST: str = "0.0.0.0"
    DEV_MODE: bool = False
    SESSION_SECRET: str = "temporary-secret-key-for-dhara-rag"

    # --- Database ---
    DATABASE_URL: str = "postgresql://redevelopment:redevelopment@localhost:5435/rag_service_db"

    # --- Vector DB (Milvus) ---
    MILVUS_HOST: str = "milvus"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "documents"
    MILVUS_COLLECTION_RAG: str = "dcpr_knowledge"
    MILVUS_URI: str = ""
    MILVUS_TOKEN: str = ""

    # --- LLM ---
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    HF_TOKEN: str = ""

    # --- Auth ---
    CLERK_JWT_KEY: str = ""
    SECRET_KEY: str = "7c995f82ba3a032a562b71010459672b6ad0710d690f9f89c82150a39300ada8"

    # --- Directories ---
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    LOGS_DIR: Path = BASE_DIR / "logs"

    class Config(BaseServiceSettings.Config):
        env_file = BaseServiceSettings.get_env_file(__file__)


settings = Settings()
