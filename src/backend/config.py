"""
应用配置管理
"""
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from functools import lru_cache


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """应用配置"""

    # API 配置
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = True

    # LLM 提供方（OpenAI 兼容端点，如 pincc.ai、官方 OpenAI、vLLM 等）
    provider_base_url: str = Field(default="", env="PROVIDER_BASE_URL")
    provider_auth_token: str = Field(default="", env="PROVIDER_AUTH_TOKEN")
    model_name: str = Field(default="claude-haiku-4-5-20251001", env="MODEL_NAME")
    llm_timeout: float = 60.0

    # 数据库配置
    database_url: str = "postgresql://user:password@localhost:5432/knowledge_integration"
    sqlalchemy_echo: bool = False

    # Redis 配置
    redis_url: str = "redis://localhost:6379/0"

    # Neo4j 配置
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # 向量嵌入模型
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_device: str = "cpu"

    # 文件上传配置
    max_upload_size: int = 500_000_000  # 500MB
    upload_dir: str = str(PROJECT_ROOT / "data" / "textbooks")

    # 日志配置
    log_level: str = "INFO"
    log_file: str = "./logs/app.log"

    # 前端配置
    frontend_url: str = "http://localhost:3000"

    @field_validator("upload_dir", "log_file", mode="after")
    @classmethod
    def _anchor_to_project_root(cls, v: str) -> str:
        """相对路径统一锚定到 PROJECT_ROOT，避免 cwd 漂移"""
        p = Path(v)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return str(p.resolve())

    # RAG 配置
    chunk_size: int = 600
    chunk_overlap: int = 100
    top_k_retrieval: int = 5
    similarity_threshold: float = 0.75

    # 整合配置
    target_compression_ratio: float = 0.30  # 目标压缩比 30%
    alignment_similarity_threshold: float = 0.85  # 对齐相似度阈值

    class Config:
        env_file = str(ENV_FILE)
        case_sensitive = False
        protected_namespaces = ()


@lru_cache()
def get_settings() -> Settings:
    """获取应用配置（缓存）"""
    return Settings()


settings = get_settings()
