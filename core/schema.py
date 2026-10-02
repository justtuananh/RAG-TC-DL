"""Schema dùng chung của backend.

1. Cấu hình: mô hình pydantic khớp từng mục của config/settings.yaml. Khóa lạ hoặc
   sai kiểu làm dừng ngay lúc nạp (extra="forbid"), không chạy với cấu hình hỏng.
2. Dữ liệu đi giữa các tầng: Chunk (ingestion → embedding / vectorstore).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, SecretStr

LlmRole = Literal["chat", "intent", "extraction"]


def _blank_to_none(value: object) -> object:
    return None if isinstance(value, str) and not value.strip() else value


OptionalStr = Annotated[str | None, BeforeValidator(_blank_to_none)]
OptionalSecret = Annotated[SecretStr | None, BeforeValidator(_blank_to_none)]
Positive = Annotated[int, Field(gt=0)]
NonNegative = Annotated[int, Field(ge=0)]
PositiveFloat = Annotated[float, Field(gt=0)]
Temperature = Annotated[float, Field(ge=0)]


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AppSettings(_Section):
    env: Literal["development", "production"]
    startup_checks: bool


class PathSettings(_Section):
    source_dir: Path
    markdown_dir: Path


class ServiceSettings(_Section):
    embedding_url: str
    rerank_url: str
    qdrant_url: str
    ollama_url: str


class EmbeddingModel(_Section):
    name: str
    vector_size: Positive


class RerankerModel(_Section):
    name: str
    max_length: Positive


class ModelSettings(_Section):
    embedding: EmbeddingModel
    reranker: RerankerModel
    llm_chat: str
    llm_intent: OptionalStr = None
    llm_extraction: OptionalStr = None


class EmbeddingSettings(_Section):
    query_timeout_s: PositiveFloat
    batch_size: Positive
    batch_timeout_s: PositiveFloat


class VectorStoreSettings(_Section):
    collection: str
    upsert_batch: Positive


class ChunkingSettings(_Section):
    synth_section_chars: Positive
    max_table_rows: Positive
    table_group_rows: Positive


class RetrievalSettings(_Section):
    top_k: Positive
    top_n: Positive
    rerank_pool: Positive
    rrf_k: Positive
    min_routed_candidates: NonNegative


class RerankingSettings(_Section):
    timeout_s: PositiveFloat
    doc_cap_chars: Positive
    doc_back_chars: NonNegative


class ChatLlmSettings(_Section):
    timeout_s: PositiveFloat
    num_ctx: Positive
    max_new_tokens: Positive
    temperature: Temperature
    keep_alive: str
    history_turns: NonNegative


class ContextSettings(_Section):
    chars_per_token: Positive
    prompt_reserve_tokens: Positive
    max_block_chars: Positive
    min_block_chars: Positive
    source_abs_floor: Annotated[float, Field(ge=0)]
    source_rel_floor: Annotated[float, Field(ge=0, le=1)]


class AuxLlmSettings(_Section):
    """Lời gọi LLM phụ (phân loại intent, trích xuất §6): URL rỗng = dùng URL chung."""

    enabled: bool
    url: OptionalStr = None
    timeout_s: PositiveFloat
    num_ctx: Positive
    temperature: Temperature
    keep_alive: str


class LlmSettings(_Section):
    chat: ChatLlmSettings
    context: ContextSettings
    intent: AuxLlmSettings
    extraction: AuxLlmSettings

    @property
    def total_context_chars(self) -> int:
        """Trần tổng ký tự ngữ cảnh: phần num_ctx còn lại sau prompt, quy ra ký tự."""
        return (self.chat.num_ctx - self.context.prompt_reserve_tokens) * self.context.chars_per_token


class IngestionSettings(_Section):
    soffice_bin: OptionalStr = None
    convert_timeout_s: PositiveFloat
    max_upload_bytes: Positive
    marker_python: OptionalStr = None


class DatabaseSettings(_Section):
    url: OptionalSecret = None
    host: str
    port: Positive
    name: str
    user: str
    password: SecretStr


class AuthSettings(_Section):
    enabled: bool
    jwt_secret_key: OptionalSecret = None
    jwt_algorithm: str
    jwt_expiration_hours: Positive


class ApiSettings(_Section):
    host: str
    port: Positive
    cors_origins: tuple[str, ...]


class QuerySettings(_Section):
    list_limit_max: Positive
    export_limit_max: Positive
    catalog_row_limit: Positive
    trend_point_cap: Positive
    cache_ttl_s: PositiveFloat


class Settings(_Section):
    app: AppSettings
    paths: PathSettings
    services: ServiceSettings
    models: ModelSettings
    embedding: EmbeddingSettings
    vectorstore: VectorStoreSettings
    chunking: ChunkingSettings
    retrieval: RetrievalSettings
    reranking: RerankingSettings
    llm: LlmSettings
    ingestion: IngestionSettings
    database: DatabaseSettings
    auth: AuthSettings
    api: ApiSettings
    query: QuerySettings

    def llm_model(self, role: LlmRole) -> str:
        """Model cho một vai trò; intent/extraction để trống thì dùng model chat."""
        specific = {"intent": self.models.llm_intent, "extraction": self.models.llm_extraction}
        return specific.get(role) or self.models.llm_chat

    def llm_url(self, role: LlmRole) -> str:
        """URL Ollama cho một vai trò; intent/extraction để trống thì dùng URL chung."""
        specific = {"intent": self.llm.intent.url, "extraction": self.llm.extraction.url}
        return specific.get(role) or self.services.ollama_url


@dataclass
class Chunk:
    """Một đơn vị index: section cha (ngữ cảnh) hoặc đoạn con (được nhúng + tìm)."""

    chunk_id: str               # sha256[:16] của (file + section + text)
    parent_id: str | None       # None với chunk cha
    is_parent: bool
    kind: str                   # "section" | "paragraph" | "table" | "formula"
    text: str                   # nội dung (chunk cha có tiền tố heading)
    section_path: str           # vd. "3 Các phép kiểm định > 3.1 Phép đo"
    file_stem: str              # stem của file .md nguồn (= tên docx)
