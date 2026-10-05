"""Giá trị mặc định mà eval và service phụ thuộc: đổi là phải chạy lại eval."""

from core.settings_loader import load_settings


def test_defaults_eval_depends_on():
    s = load_settings(env={})
    assert s.models.embedding.vector_size == 1024
    assert s.vectorstore.collection == "qtkd_rag"
    assert s.retrieval.rrf_k == 60
    assert s.retrieval.rrf_weight_dense == 1.0
    assert s.retrieval.rrf_weight_bm25 == 1.0
    assert s.retrieval.top_k == 50
    assert s.retrieval.rerank_pool == 60
    assert s.llm.chat.history_turns == 3
    assert s.llm.chat.num_ctx == 8192


def test_context_budget_formula_and_bounds():
    """Ngữ cảnh + prompt + câu trả lời phải vừa num_ctx: Ollama cắt prompt quá dài.

    Đo 2026-10-05 (qwen2.5:7b): prompt không ngữ cảnh 450 token, ngữ cảnh QTKĐ 2,54
    ký tự/token; công thức cũ (không trừ max_new_tokens, 3 ký tự/token) cho 20 976 ký tự,
    đủ cả 5 mục của câu diện tích hiệu dụng thì prompt chạm đúng 8 191/8 192 token.
    """
    llm = load_settings(env={}).llm
    tokens = llm.chat.num_ctx - llm.context.prompt_reserve_tokens - llm.chat.max_new_tokens
    assert llm.total_context_chars == int(tokens * llm.context.chars_per_token)
    assert llm.context.chars_per_token <= 2.54
    assert llm.total_context_chars > 1800
    assert llm.context.min_block_chars < llm.context.max_block_chars < llm.total_context_chars


def test_intent_classifier_shares_chat_context_window():
    s = load_settings(env={})
    assert s.llm.intent.num_ctx == s.llm.chat.num_ctx  # Ollama không nạp lại model giữa hai lời gọi


def test_role_models_fall_back_to_chat_model():
    s = load_settings(env={"OLLAMA_MODEL": "m-chat"})
    assert s.llm_model("intent") == "m-chat"
    assert s.llm_model("extraction") == "m-chat"
    s2 = load_settings(env={"OLLAMA_MODEL": "m-chat", "SECTION6_LLM_MODEL": "m-ext"})
    assert s2.llm_model("extraction") == "m-ext"


def test_role_urls_fall_back_to_service_url():
    s = load_settings(
        env={"OLLAMA_URL": "http://o:11434/api/chat", "INTENT_OLLAMA_URL": "http://i/api/chat"}
    )
    assert s.llm_url("chat") == "http://o:11434/api/chat"
    assert s.llm_url("intent") == "http://i/api/chat"
    assert s.llm_url("extraction") == "http://o:11434/api/chat"


def test_secrets_are_secretstr():
    s = load_settings(env={"JWT_SECRET_KEY": "k", "POSTGRES_PASSWORD": "p"})
    assert "'k'" not in repr(s.auth)
    assert s.auth.jwt_secret_key.get_secret_value() == "k"
    assert s.database.password.get_secret_value() == "p"
