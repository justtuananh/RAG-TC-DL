import pytest

from reranking import reranker


@pytest.fixture(autouse=True)
def _reset_rerank_batch_state():
    """Cỡ lô thích nghi là trạng thái module: không để test này ảnh hưởng test khác."""
    reranker._state.update(cap=None, ok_streak=0, fails=0)
    yield
    reranker._state.update(cap=None, ok_streak=0, fails=0)
