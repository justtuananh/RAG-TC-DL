"""Guard chống lệch hằng số rải rác khắp 4+ module (CLAUDE.md: phải đổi đồng bộ).

VECTOR_SIZE phải khớp service embedding; COLLECTION phải thống nhất; k của RRF và
độ rộng phễu là thứ eval phụ thuộc; hằng app khớp magic number trong test LLM.
"""

import inspect

import generation
import index.embed_store as ES
import retrieval.bm25_index as BM
import retrieval.retriever as RET
import retrieval.router as RT


def test_vector_size_matches_embedding_service():
    assert ES.VECTOR_SIZE == 1024


def test_collection_name_consistent_everywhere():
    assert ES.COLLECTION == RET.COLLECTION == BM.COLLECTION == RT.COLLECTION == "qtkd_rag"


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
