"""Ánh xạ lỗi nghiệp vụ của tầng review và tra cứu dữ liệu thành HTTPException."""

from __future__ import annotations

from fastapi import HTTPException

import review.queue as review
from query import provenance as provenance_query
from query import records as data_query


def review_http_error(exc: review.ReviewError) -> HTTPException:
    if isinstance(exc, review.NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, review.ConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


def data_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, data_query.NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (data_query.QueryError, provenance_query.ProvenanceError)):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))
