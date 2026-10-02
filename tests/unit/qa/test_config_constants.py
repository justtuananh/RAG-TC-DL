"""Guard chống lệch hằng số rải rác khắp 4+ module (CLAUDE.md: phải đổi đồng bộ).

k của RRF và độ rộng phễu là thứ eval phụ thuộc; hằng app khớp magic number
trong test LLM. VECTOR_SIZE/COLLECTION nay là cấu hình duy nhất ở
tests/unit/core/test_settings_values.py.
"""

import inspect

import generation
import retrieval.retriever as RET


def test_rrf_k_default_is_60():
    assert inspect.signature(RET.rrf_fuse).parameters["k"].default == 60


def test_funnel_widths():
    assert RET.TOP_K == 50
    assert RET.RERANK_POOL == 60


def test_generation_llm_constants():
    assert generation.HISTORY_TURNS == 3
    assert generation.NUM_CTX == 8192
    # Ngân sách ngữ cảnh động phải khớp công thức + lớn hơn cap cứng 1800 cũ + có sàn.
    assert generation.TOTAL_CONTEXT_CHARS == (
        (generation.NUM_CTX - generation.PROMPT_RESERVE_TOKENS) * generation.CHARS_PER_TOKEN
    )
    assert generation.TOTAL_CONTEXT_CHARS > 1800
    # Cap mỗi nguồn phải nằm giữa sàn và trần tổng (đo thực nghiệm: tránh nhồi ~20k).
    assert generation.MIN_BLOCK_CHARS < generation.MAX_BLOCK_CHARS < generation.TOTAL_CONTEXT_CHARS
