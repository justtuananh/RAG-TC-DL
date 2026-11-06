"""Schema dùng chung của backend.

1. Cấu hình: mô hình pydantic khớp từng mục của config/settings.yaml. Khóa lạ hoặc
   sai kiểu làm dừng ngay lúc nạp (extra="forbid"), không chạy với cấu hình hỏng.
2. Dữ liệu đi giữa các tầng: Chunk (ingestion → embedding / vectorstore).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, SecretStr, model_validator

LlmRole = Literal["chat"]


def _blank_to_none(value: object) -> object:
    return None if isinstance(value, str) and not value.strip() else value


OptionalStr = Annotated[str | None, BeforeValidator(_blank_to_none)]
OptionalSecret = Annotated[SecretStr | None, BeforeValidator(_blank_to_none)]
Positive = Annotated[int, Field(gt=0)]
NonNegative = Annotated[int, Field(ge=0)]
PositiveFloat = Annotated[float, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]
Temperature = Annotated[float, Field(ge=0)]


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AppSettings(_Section):
    env: Literal["development", "production"]
    startup_checks: bool


class PathSettings(_Section):
    source_dir: Path
    markdown_dir: Path
    formula_registry_db: Path


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
    top_n_per_file: Positive
    rerank_pool: Positive
    # Câu hỏi không nêu thiết bị: lấy tốt nhất MỖI tài liệu (0 = tắt) để trả lời đủ các tài liệu.
    coverage_per_file: NonNegative = 0
    coverage_pool_per_file: Positive = 6
    coverage_max_sources: Positive = 10
    rrf_k: Positive
    rrf_weight_dense: NonNegativeFloat
    rrf_weight_bm25: NonNegativeFloat
    min_routed_candidates: NonNegative

    @model_validator(mode="after")
    def _not_both_weights_zero(self) -> RetrievalSettings:
        """Cả hai trọng số bằng 0 thì điểm RRF luôn 0, hoàn toàn mất thứ tự."""
        if self.rrf_weight_dense == 0 and self.rrf_weight_bm25 == 0:
            raise ValueError("rrf_weight_dense và rrf_weight_bm25 không được cùng bằng 0")
        return self


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
    chars_per_token: PositiveFloat
    prompt_reserve_tokens: Positive
    max_block_chars: Positive
    min_block_chars: Positive
    quote_anchors: Positive
    formula_line_slack: Positive
    linearize_tables: bool = True
    source_abs_floor: Annotated[float, Field(ge=0)]
    source_rel_floor: Annotated[float, Field(ge=0, le=1)]


class RewriteSettings(_Section):
    """Viết lại câu hỏi tiếp theo thành câu độc lập (hội thoại nhiều lượt)."""

    enabled: bool = True
    max_history_turns: Positive = 2
    answer_chars: Positive = 300
    max_query_chars: Positive = 400
    num_predict: Positive = 120
    timeout_s: PositiveFloat = 30


class MultiDocumentSettings(_Section):
    """Câu hỏi không chỉ định một QTKĐ (chung chung hoặc nêu ≥ 2 QTKĐ): trả lời theo từng tài liệu."""

    enabled: bool = True
    min_documents: Positive = 2           # ít hơn số tài liệu này thì trả lời một lượt như thường
    max_documents: Positive = 6           # trần số tài liệu xét bổ sung
    max_followups: Positive = 4           # trần số lượt hỏi riêng sau câu trả lời chung (giữ p95)
    context_chars: Positive = 5000        # trần ngữ cảnh mỗi lượt (chỉ nguồn của một tài liệu)
    num_predict: Positive = 120           # trần token mỗi lượt hỏi riêng
    merge_identical: bool = True          # tài liệu cùng bộ số liệu gộp một dòng
    merge_max_chars: Positive = 80        # giá trị dùng ở dòng gộp dài hơn mức này thì không gộp


class NumberCheckSettings(_Section):
    """Kiểm số liệu trong câu trả lời so với nguồn; sinh lại khi có số không có trong nguồn."""

    enabled: bool = True
    max_regen: NonNegative = 1


class CitationSettings(_Section):
    """Khối 'Nguồn:' dựng tất định từ các nguồn được [n] tham chiếu (llm/citations.py)."""

    enabled: bool = True
    min_keyword_len: Positive = 5          # từ khóa của câu trả lời: chữ có ít nhất N ký tự
    min_keyword_hits: Positive = 2         # số từ khóa tối thiểu có trong nguồn khi câu trả lời không có số
    max_auto_sources: Positive = 1         # số nguồn tự gắn khi câu trả lời thiếu [n]


class LlmSettings(_Section):
    chat: ChatLlmSettings
    context: ContextSettings
    rewrite: RewriteSettings = Field(default_factory=RewriteSettings)
    number_check: NumberCheckSettings = Field(default_factory=NumberCheckSettings)
    citation: CitationSettings = Field(default_factory=CitationSettings)
    multi_document: MultiDocumentSettings = Field(default_factory=MultiDocumentSettings)

    @property
    def total_context_chars(self) -> int:
        """Trần tổng ký tự ngữ cảnh: phần num_ctx còn lại sau prompt (hệ thống + câu hỏi +
        lịch sử) VÀ câu trả lời, quy ra ký tự."""
        tokens = self.chat.num_ctx - self.context.prompt_reserve_tokens - self.chat.max_new_tokens
        return int(tokens * self.context.chars_per_token)


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


class CalcSettings(_Section):
    """Tính trong chat bằng công thức ĐÃ DUYỆT (formula_registry); công thức nháp không bao giờ được dùng."""

    enabled: bool = True
    intent_pattern: str = r"\b(tính|quy đổi|đổi sang|xác định|hiệu chỉnh|chuyển đổi)\b"
    max_formulas: Positive = 3
    min_variable_coverage: Annotated[float, Field(ge=0, le=1)] = 0.6
    num_predict: Positive = 300
    timeout_s: PositiveFloat = 60


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
    calc: CalcSettings = Field(default_factory=CalcSettings)

    def llm_model(self, role: LlmRole) -> str:
        """Model chat (vai trò LLM duy nhất còn lại)."""
        return self.models.llm_chat

    def llm_url(self, role: LlmRole) -> str:
        """URL Ollama (vai trò LLM duy nhất còn lại)."""
        return self.services.ollama_url


@dataclass
class Chunk:
    """Một đơn vị index: section cha (ngữ cảnh) hoặc đoạn con (được nhúng + tìm)."""

    chunk_id: str  # sha256[:16] của (file + section + text)
    parent_id: str | None  # None với chunk cha
    is_parent: bool
    kind: str  # "section" | "paragraph" | "table" | "formula"
    text: str  # nội dung (chunk cha có tiền tố heading)
    section_path: str  # vd. "3 Các phép kiểm định > 3.1 Phép đo"
    file_stem: str  # stem của file .md nguồn (= tên docx)
