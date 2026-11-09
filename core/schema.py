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
    qdrant_api_key: OptionalSecret = None
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
    # Gắn mục con đánh số (6.3.2...) chứa đoạn khớp vào đường dẫn nguồn hiển thị.
    locate_subsection: bool = False
    subsection_title_chars: Positive = 120

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
    # Chia lô khi gọi cross-encoder: GPU dùng chung nên một lô lớn dễ CUDA OOM (HTTP 500).
    batch_size: Positive = 8  # số cặp tối đa mỗi lần gọi (<= 32)
    batch_max_chars: Positive = 12000  # tổng ký tự document tối đa mỗi lô
    max_doc_chars: Positive = 1500  # cắt mỗi document trước khi gửi
    min_batch_pause_s: NonNegativeFloat = 0.0  # nghỉ giữa các lô


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
    linearize_value_tables: bool = True   # bảng tra giá trị không có cột TT -> dòng 'nhãn hàng: nhãn cột = giá trị'
    long_table_rows: Annotated[int, Field(ge=0)] = 12  # bảng dài hơn: chỉ giữ dòng khớp từ khóa câu hỏi (0 = tắt)
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
    extractive_enabled: bool = False
    evidence_per_document: Positive = 3
    evidence_candidates_per_source: Positive = 12
    evidence_max_candidates: Positive = 96
    evidence_min_score: Annotated[float, Field(ge=0, le=1)] = 0.35
    evidence_relative_floor: Annotated[float, Field(ge=0, le=1)] = 0.35
    min_documents: Positive = 2           # ít hơn số tài liệu này thì trả lời một lượt như thường
    max_documents: Positive = 6           # trần số tài liệu xét bổ sung
    max_followups: Positive = 2           # trần số lượt hỏi riêng sau câu trả lời chung (giữ p95)
    max_followups_named: Positive = 4     # trần khi câu hỏi nêu rõ ≥ 2 QTKĐ (mọi tài liệu được nêu đều đáng hỏi)
    min_followup_score: Annotated[float, Field(ge=0, le=1)] = 0.3  # câu chung: chỉ hỏi tài liệu có nguồn rerank_score ≥ mức này
    time_budget_s: PositiveFloat = 6.0    # quá ngần này giây từ lúc bắt đầu sinh thì bỏ các lượt hỏi riêng còn lại
    generic_device_words: tuple[str, ...] = ()  # từ đầu tên thiết bị quá chung, không tính là nêu một loại thiết bị
    context_chars: Positive = 5000        # trần ngữ cảnh mỗi lượt (chỉ nguồn của một tài liệu)
    num_predict: Positive = 90            # trần token mỗi lượt hỏi riêng
    merge_identical: bool = True          # tài liệu cùng bộ số liệu gộp một dòng
    merge_max_chars: Positive = 80        # giá trị dùng ở dòng gộp dài hơn mức này thì không gộp
    grounding_min_coverage: Annotated[float, Field(ge=0, le=1)] = 0.6          # trích thay cho sinh: tỷ lệ từ khóa câu hỏi phải có trong đoạn trích
    grounding_min_coverage_refusal: Annotated[float, Field(ge=0, le=1)] = 0.8  # trích thay cho câu từ chối: chặt hơn
    grounding_absent_term_coverage: Annotated[float, Field(ge=0, le=1)] = 0.9  # có từ khóa vắng khỏi mọi nguồn thì cần phủ ≥ mức này
    grounding_stop_words: tuple[str, ...] = ()  # từ hỏi/từ chức năng không tính là từ khóa đối tượng


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
    marker_device: Literal["cuda", "cpu"]
    marker_pages_per_run: Positive
    marker_memory_max_mb: NonNegative
    marker_threads: Positive


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
    convert_enabled: bool = True          # câu quy đổi đơn vị thuần túy: trả lời tất định bằng bảng UNITS, không qua LLM
    convert_verbs: str = r"quy đổi|chuyển đổi|đổi|chuyển"  # động từ đứng trước "<số> <đv> sang <đv>"


class ObjectScopeSettings(_Section):
    """Từ chối khi câu hỏi về quy trình/điều kiện kiểm định của một đối tượng không thuộc các QTKĐ trong kho."""

    enabled: bool = True
    trigger_pattern: str = r"quy trình|trình tự|phép kiểm định|điều kiện|chu kỳ|phương pháp|yêu cầu|nội dung|thời hạn"
    scope_section_pattern: str = r"phạm vi áp dụng"  # mục nguồn nêu đối tượng được kiểm định (ngoài tiêu đề tài liệu)
    generic_words: tuple[str, ...] = ()   # từ chỉ loại chung ("thiết bị", "đo"...): không đủ để nhận diện đối tượng
    ignore_words: tuple[str, ...] = ()    # từ chức năng/đại từ đứng sau "kiểm định" (này, lại, định kỳ...)
    stop_words: tuple[str, ...] = ()      # từ kết thúc cụm tên đối tượng (gồm, là, có, cần...)


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
    object_scope: ObjectScopeSettings = Field(default_factory=ObjectScopeSettings)

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
