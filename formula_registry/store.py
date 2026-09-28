"""Transactional registry. Draft generation cannot approve or execute a formula."""

import copy
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from formula_lab.engine import calculate

from .validation import executable_spec, validate, validate_shape

ROOT = Path(__file__).resolve().parents[1]


class Conflict(ValueError):
    pass


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def timestamp():
    return datetime.now(UTC).isoformat()


class Registry:
    def __init__(self, path=None):
        self.path = Path(
            path
            or os.environ.get('FORMULA_REGISTRY_DB', ROOT / '.formula-registry/registry.sqlite3')
        )

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.execute(
                'CREATE TABLE IF NOT EXISTS formulas (id TEXT PRIMARY KEY, document_id TEXT NOT NULL, record TEXT NOT NULL)'
            )
            db.execute('CREATE INDEX IF NOT EXISTS formulas_document ON formulas(document_id)')
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _load(db, id):
        row = db.execute('SELECT record FROM formulas WHERE id=?', (id,)).fetchone()
        if row is None:
            raise KeyError(id)
        return json.loads(row['record'])

    @staticmethod
    def _write(db, record):
        db.execute(
            'INSERT OR REPLACE INTO formulas VALUES (?,?,?)',
            (record['id'], record['source']['document_id'], json.dumps(record, ensure_ascii=False)),
        )

    @staticmethod
    def _fresh(record):
        path = Path(record['_source_path'])
        if not path.is_absolute():
            path = ROOT / path
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest() == record['source']['sha256']
        except OSError:
            return False

    def _public(self, record):
        value = {k: v for k, v in record.items() if not k.startswith('_')}
        if not self._fresh(record):
            value['status'] = 'stale'
        value['validation_errors'] = validate(value['proposal'])
        return value

    def add(self, source_path, document_id, source_hash, candidates):
        source_path = Path(source_path).resolve()
        stored_path = (
            str(source_path.relative_to(ROOT))
            if source_path.is_relative_to(ROOT)
            else str(source_path)
        )
        if hashlib.sha256(source_path.read_bytes()).hexdigest() != source_hash:
            raise Conflict('Tài liệu thay đổi trong lúc trích xuất; hãy xử lý lại.')
        created = 0
        with self.connection() as db:
            for row in db.execute(
                'SELECT record FROM formulas WHERE document_id=?', (document_id,)
            ).fetchall():
                old = json.loads(row['record'])
                if old['source']['sha256'] != source_hash and old['status'] != 'stale':
                    old['status'] = 'stale'
                    old['revision'] += 1
                    old['history'].append(
                        dict(action='source_superseded', at=timestamp(), revision=old['revision'])
                    )
                    self._write(db, old)
            for candidate in candidates:
                source = dict(
                    candidate['source'],
                    document_id=document_id,
                    file=source_path.name,
                    sha256=source_hash,
                )
                id = digest([document_id, source_hash, source['fid']])[:32]
                if db.execute('SELECT 1 FROM formulas WHERE id=?', (id,)).fetchone():
                    existing = self._load(db, id)
                    existing['_source_path'] = stored_path
                    if existing['status'] == 'stale':
                        # Restoring the same bytes starts a new review, never restores approval.
                        existing['status'] = 'pending_review'
                        existing['revision'] += 1
                        existing['review'] = None
                        existing['_approved_digest'] = None
                        existing['history'].append(
                            dict(
                                action='source_restored_for_review',
                                at=timestamp(),
                                revision=existing['revision'],
                            )
                        )
                        created += 1
                    self._write(db, existing)
                    continue  # Active records retain their edits, rejections and approvals.
                record = dict(
                    id=id,
                    source=source,
                    proposal=candidate['proposal'],
                    warnings=candidate['warnings'],
                    status='pending_review',
                    revision=1,
                    created_at=timestamp(),
                    review=None,
                    history=[dict(action='draft_created', at=timestamp(), revision=1)],
                    _source_path=stored_path,
                    _approved_digest=None,
                )
                self._write(db, record)
                created += 1
        return created

    def list(self, document_id):
        with self.connection() as db:
            records = [
                json.loads(row['record'])
                for row in db.execute(
                    'SELECT record FROM formulas WHERE document_id=? ORDER BY id', (document_id,)
                )
            ]
        return sorted(
            (self._public(r) for r in records), key=lambda r: (r['source']['fid'], r['created_at'])
        )

    def get(self, id):
        with self.connection() as db:
            return self._public(self._load(db, id))

    def _editable(self, record, revision):
        if record['revision'] != revision:
            raise Conflict('Bản nháp đã thay đổi ở nơi khác. Hãy tải lại trước khi thao tác.')
        if record['status'] == 'stale' or not self._fresh(record):
            raise Conflict('Nguồn đã thay đổi hoặc bị xóa. Hãy tạo bản nháp từ phiên bản hiện tại.')

    def update(self, id, revision, proposal):
        if (
            not isinstance(proposal, dict)
            or len(json.dumps(proposal, ensure_ascii=False, allow_nan=False)) > 100_000
        ):
            raise ValueError('Bản nháp không hợp lệ hoặc vượt quá 100.000 ký tự.')
        # Restrict editable fields; provenance/status/review can never be client-written.
        allowed = {'title', 'expression', 'unit', 'variables', 'conditions', 'test_cases'}
        if set(proposal) != allowed:
            raise ValueError(
                'Định nghĩa cần đúng các trường title, expression, unit, variables, conditions, test_cases.'
            )
        validate_shape(proposal)
        with self.connection() as db:
            record = self._load(db, id)
            self._editable(record, revision)
            previous = copy.deepcopy(record['proposal'])
            record['proposal'] = proposal
            record['status'] = 'pending_review'
            record['revision'] += 1
            record['review'] = None
            record['_approved_digest'] = None
            record['history'].append(
                dict(
                    action='draft_updated',
                    at=timestamp(),
                    revision=record['revision'],
                    proposal_digest=digest(proposal),
                    previous_proposal=previous,
                )
            )
            self._write(db, record)
        return self._public(record)

    def decide(self, id, revision, decision, reviewer, note, confirmed):
        if decision not in ('approve', 'reject'):
            raise ValueError('Quyết định không hợp lệ.')
        if not reviewer.strip() or not note.strip():
            raise ValueError('Cần tên người rà soát và nhận xét/căn cứ quyết định.')
        if decision == 'approve' and confirmed is not True:
            raise ValueError(
                'Cần xác nhận đã đối chiếu công thức, biến, đơn vị, điều kiện và đáp án với nguồn.'
            )
        with self.connection() as db:
            record = self._load(db, id)
            self._editable(record, revision)
            if record['status'] != 'pending_review':
                raise Conflict(
                    'Chỉ bản nháp đang chờ duyệt mới được quyết định. Sửa và lưu để mở lượt duyệt mới.'
                )
            errors = validate(record['proposal']) if decision == 'approve' else []
            if errors:
                raise ValueError('\n'.join(errors))
            record['status'] = 'approved' if decision == 'approve' else 'rejected'
            record['revision'] += 1
            record['review'] = dict(
                reviewer=reviewer.strip(), note=note.strip(), at=timestamp(), decision=decision
            )
            record['_approved_digest'] = (
                digest([record['source'], record['proposal']]) if decision == 'approve' else None
            )
            record['history'].append(
                dict(
                    record['review'],
                    action=decision,
                    revision=record['revision'],
                    proposal_digest=digest(record['proposal']),
                    proposal=copy.deepcopy(record['proposal']),
                    source_sha256=record['source']['sha256'],
                )
            )
            self._write(db, record)
        return self._public(record)

    def compute(self, id, revision, inputs, confirmations):
        with self.connection() as db:
            record = self._load(db, id)
            self._editable(record, revision)
            if record['status'] != 'approved' or record['_approved_digest'] != digest(
                [record['source'], record['proposal']]
            ):
                raise Conflict('Công thức chưa được người dùng phê duyệt cho phiên bản này.')
            result = calculate(
                executable_spec(record['proposal'], id, revision), inputs, confirmations
            )
            result.update(
                source=record['source']['file'],
                source_hash=record['source']['sha256'],
                approved_by=record['review']['reviewer'],
                approved_at=record['review']['at'],
            )
            return result

    def invalidate(self, document_id):
        with self.connection() as db:
            for row in db.execute(
                'SELECT record FROM formulas WHERE document_id=?', (document_id,)
            ).fetchall():
                record = json.loads(row['record'])
                if record['status'] == 'stale':
                    continue
                record['status'] = 'stale'
                record['revision'] += 1
                record['history'].append(
                    dict(action='document_deleted', at=timestamp(), revision=record['revision'])
                )
                self._write(db, record)
