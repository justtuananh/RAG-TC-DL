import copy
import hashlib
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from formula_registry.api import router
from formula_registry.drafts import generate_from_docx, register_extraction, simple_expression
from formula_registry.store import Conflict, Registry
from formula_registry.validation import validate


def write_docx(path, expression='P=a+b'):
    with ZipFile(path, 'w') as archive:
        archive.writestr(
            '[Content_Types].xml',
            '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>''',
        )
        archive.writestr(
            '_rels/.rels',
            '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>''',
        )
        archive.writestr(
            'word/document.xml',
            f'''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><w:body><w:p><w:r><w:t>Áp suất cộng; a và b cùng đơn vị Pa, cùng điểm đo.</w:t></w:r></w:p><w:p><m:oMath><m:r><m:t>{expression}</m:t></m:r></m:oMath></w:p><w:p><w:r><w:t>P là kết quả tại điểm đo; cần đối chiếu điều kiện áp dụng.</w:t></w:r></w:p></w:body></w:document>''',
        )


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('FORMULA_REGISTRY_DB', str(tmp_path / 'registry.sqlite3'))
    source = tmp_path / 'demo.docx'
    write_docx(source)
    registry = Registry()
    generate_from_docx(source, 'demo', registry)
    return source, registry, registry.list('demo')[0]


def complete_proposal(draft):
    p = copy.deepcopy(draft['proposal'])
    p.update(
        title='Áp suất tổng',
        expression='a+b',
        unit='Pa',
        variables=[
            dict(key='a', label='Áp suất a', unit='Pa'),
            dict(key='b', label='Áp suất b', unit='Pa'),
        ],
        conditions=[dict(key='same_point', label='Cùng điểm đo, áp suất dùng đúng quy ước.')],
        test_cases=[
            dict(
                inputs={'a': {'value': '2', 'unit': 'Pa'}, 'b': {'value': '3', 'unit': 'Pa'}},
                expected='5',
                unit='Pa',
            )
        ],
    )
    return p


def approve(registry, draft):
    draft = registry.update(draft['id'], draft['revision'], complete_proposal(draft))
    return registry.decide(
        draft['id'],
        draft['revision'],
        'approve',
        'Người kiểm thử',
        'Đối chiếu nguồn và 2 + 3 = 5.',
        True,
    )


def test_extraction_is_pending_incomplete_and_cannot_compute(env):
    source, registry, draft = env
    assert draft['status'] == 'pending_review'
    assert draft['proposal']['expression'] == 'a+b'
    assert draft['source']['latex'] == 'P=a+b'
    assert draft['source']['sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert 'cùng đơn vị Pa' in draft['source']['context']
    assert draft['validation_errors']
    with pytest.raises(Conflict, match='chưa được'):
        registry.compute(draft['id'], 1, {}, {})
    with pytest.raises(ValueError):
        registry.decide(draft['id'], 1, 'approve', 'Reviewer', 'Checked', True)
    assert registry.get(draft['id'])['status'] == 'pending_review'


def test_approval_persists_with_audit_and_calculation(env):
    _, registry, draft = env
    approved = approve(registry, draft)
    registry = Registry()  # reconnect/restart
    result = registry.compute(
        draft['id'],
        approved['revision'],
        {'a': {'value': '2', 'unit': 'kPa'}, 'b': {'value': '-500', 'unit': 'Pa'}},
        {'same_point': True},
    )
    assert result['value'] == '1500' and result['unit'] == 'Pa'
    assert result['source_hash'] == draft['source']['sha256']
    assert result['approved_by'] == 'Người kiểm thử'
    assert registry.get(draft['id'])['history'][-1]['action'] == 'approve'


@pytest.mark.parametrize('decision', ['approve', 'reject'])
def test_decision_requires_actor_note_and_explicit_approval(env, decision):
    _, registry, draft = env
    draft = registry.update(draft['id'], 1, complete_proposal(draft))
    for actor, note, confirmed in [('', 'Checked', True), ('Reviewer', ' ', True)]:
        with pytest.raises(ValueError):
            registry.decide(draft['id'], 2, decision, actor, note, confirmed)
    if decision == 'approve':
        with pytest.raises(ValueError):
            registry.decide(draft['id'], 2, decision, 'Reviewer', 'Checked', False)
    else:
        rejected = registry.decide(
            draft['id'], 2, decision, 'Reviewer', 'Insufficient source', False
        )
        assert rejected['status'] == 'rejected'
        with pytest.raises(Conflict):
            registry.compute(draft['id'], rejected['revision'], {}, {})


def test_edit_approved_revokes_execution_and_requires_new_decision(env):
    _, registry, draft = env
    approved = approve(registry, draft)
    edited = registry.update(draft['id'], approved['revision'], complete_proposal(draft))
    assert edited['status'] == 'pending_review' and edited['review'] is None
    with pytest.raises(Conflict):
        registry.compute(draft['id'], approved['revision'], {}, {})
    with pytest.raises(Conflict):
        registry.compute(draft['id'], edited['revision'], {}, {})


def test_concurrent_approvals_only_one_wins(env):
    _, registry, draft = env
    edited = registry.update(draft['id'], 1, complete_proposal(draft))

    def decide():
        try:
            return registry.decide(
                draft['id'], edited['revision'], 'approve', 'Reviewer', 'Checked', True
            )['status']
        except Conflict:
            return 'conflict'

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: decide(), range(2)))
    assert sorted(results) == ['approved', 'conflict']


@pytest.mark.parametrize('kind', ['changed', 'deleted'])
def test_source_change_or_deletion_blocks_approval_and_compute(env, kind):
    source, registry, draft = env
    approved = approve(registry, draft)
    if kind == 'changed':
        write_docx(source, 'P=a-b')
    else:
        source.unlink()
    assert registry.get(draft['id'])['status'] == 'stale'
    with pytest.raises(Conflict, match='Nguồn'):
        registry.compute(draft['id'], approved['revision'], {}, {})
    with pytest.raises(Conflict, match='Nguồn'):
        registry.update(draft['id'], approved['revision'], complete_proposal(draft))


def test_reingestion_is_idempotent_and_preserves_review(env):
    source, registry, draft = env
    approved = approve(registry, draft)
    assert generate_from_docx(source, 'demo', registry)['created'] == 0
    assert registry.get(draft['id']) == approved
    write_docx(source, 'P=a-b')
    assert generate_from_docx(source, 'demo', registry)['created'] == 1
    rows = registry.list('demo')
    assert len(rows) == 2
    assert sorted(r['status'] for r in rows) == ['pending_review', 'stale']


@pytest.mark.parametrize(
    'mutate',
    [
        lambda p: p.update(expression='__import__("os").system("id")'),
        lambda p: p.update(expression='a[0]'),
        lambda p: p.update(expression='a**999'),
        lambda p: p.update(expression='a+unknown'),
        lambda p: p.update(unit={}),
        lambda p: p.update(variables=[None]),
        lambda p: p['variables'][0].update(unit=[]),
        lambda p: p['variables'][0].update(min='NaN'),
        lambda p: p['variables'][0].update(kind='series', min_items=2, max_items=1),
        lambda p: p['variables'][0].update(exclusive_min='false'),
        lambda p: p['test_cases'][0].update(expected='6'),
        lambda p: p['test_cases'][0].update(expected='NaN'),
        lambda p: p.update(conditions=[]),
    ],
)
def test_invalid_or_wrong_definitions_never_approve(env, mutate):
    _, registry, draft = env
    proposal = complete_proposal(draft)
    mutate(proposal)
    assert validate(proposal)
    with pytest.raises(ValueError):
        draft = registry.update(draft['id'], 1, proposal)
        registry.decide(draft['id'], draft['revision'], 'approve', 'Reviewer', 'Checked', True)


def test_registry_digest_detects_unapproved_storage_mutation(env):
    _, registry, draft = env
    approved = approve(registry, draft)
    with registry.connection() as db:
        record = registry._load(db, draft['id'])
        record['proposal']['expression'] = 'a-b'
        registry._write(db, record)
    with pytest.raises(Conflict):
        registry.compute(draft['id'], approved['revision'], {}, {})


@pytest.mark.parametrize(
    'latex,expected',
    [
        (r'z=\frac{x}{y}', '((x)/(y))'),
        (r'z=\sqrt{x}', 'sqrt(x)'),
        ('z=x+X', ''),
        (r'z=\sum{x}', ''),
        ('x=x=y', ''),
        ('z=__import__("os")', ''),
    ],
)
def test_conservative_suggestions(latex, expected):
    assert simple_expression(latex)[0] == expected


def test_api_lifecycle_conflicts_and_status_cannot_be_forged(env):
    _, registry, draft = env
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert (
            client.get('/api/documents/demo/formula-drafts').json()['drafts'][0]['status']
            == 'pending_review'
        )
        url = '/api/formula-drafts/' + draft['id']
        assert (
            client.post(
                url + '/calculate', json={'revision': 1, 'inputs': {}, 'confirmations': {}}
            ).status_code
            == 409
        )
        assert (
            client.put(
                url,
                json={'revision': 1, 'proposal': complete_proposal(draft), 'status': 'approved'},
            ).status_code
            == 422
        )
        edited = client.put(url, json={'revision': 1, 'proposal': complete_proposal(draft)}).json()
        body = dict(
            revision=edited['revision'], reviewer='Reviewer', note='Checked', confirmed=True
        )
        approved = client.post(url + '/approve', json=body)
        assert approved.status_code == 200
        assert client.post(url + '/approve', json=body).status_code == 409
        assert (
            client.post(
                url + '/calculate',
                json={'revision': approved.json()['revision'], 'inputs': {}, 'confirmations': {}},
            ).status_code
            == 422
        )
        assert '_source_path' not in client.get(url).json()


def test_ingestion_creates_drafts_before_embedding_failure(env, tmp_path, monkeypatch):
    import ingestion_jobs as jobs

    source, registry, _ = env
    source = source.with_name('another_document.docx')
    write_docx(source)
    out = tmp_path / 'extracted'
    out.mkdir()
    monkeypatch.setattr(jobs, 'OUT_DIR', out)
    monkeypatch.setattr(jobs, 'REPORT_PATH', out / 'report.json')
    monkeypatch.setattr(jobs, '_jobs', {})
    monkeypatch.setattr(jobs, 'parse_file', lambda path: [])
    monkeypatch.setattr(jobs, 'QdrantClient', Mock(side_effect=OSError('offline')))
    jobs._run_job('another_document', source)
    assert jobs._get_job('another_document').stage == 'error'
    assert registry.list('another_document')[0]['status'] == 'pending_review'


def test_missing_equation_extraction_still_creates_incomplete_draft(env):
    source, registry, _ = env
    count = register_extraction(
        source,
        'unreadable',
        hashlib.sha256(source.read_bytes()).hexdigest(),
        {'formula_detail': [{'fid': 'F099', 'kind': 'ole', 'latex': None}]},
        '',
        registry,
    )
    assert count['created'] == 1
    draft = registry.list('unreadable')[0]
    assert not draft['proposal']['expression'] and draft['validation_errors']


def test_source_paths_survive_repository_relocation(env, tmp_path, monkeypatch):
    import formula_registry.store as store

    source, registry, draft = env
    monkeypatch.setattr(store, 'ROOT', source.parent)
    generate_from_docx(source, 'demo', registry)
    approved = approve(registry, draft)
    relocated = tmp_path / 'relocated'
    relocated.mkdir()
    (relocated / source.name).write_bytes(source.read_bytes())
    source.unlink()
    monkeypatch.setattr(store, 'ROOT', relocated)
    assert registry.get(approved['id'])['status'] == 'approved'
    result = registry.compute(
        approved['id'],
        approved['revision'],
        {'a': {'value': '2', 'unit': 'Pa'}, 'b': {'value': '3', 'unit': 'Pa'}},
        {'same_point': True},
    )
    assert result['value'] == '5'


@pytest.mark.parametrize(
    'mutate',
    [
        lambda p: p.update(variables=None),
        lambda p: p.update(variables=[None]),
        lambda p: p.update(conditions=None),
        lambda p: p.update(conditions=[None]),
        lambda p: p.update(test_cases=None),
        lambda p: p.update(test_cases=[None]),
        lambda p: p.update(title={'bad': 'object'}),
        lambda p: p['test_cases'][0].update(inputs=None),
        lambda p: p['test_cases'][0]['inputs'].update(a=None),
        lambda p: p['test_cases'][0]['inputs']['a'].update(value=[None]),
    ],
)
def test_malformed_shape_rejected_without_mutating_approved_record(env, mutate):
    _, registry, draft = env
    approved = approve(registry, draft)
    proposal = complete_proposal(draft)
    mutate(proposal)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.put(
            '/api/formula-drafts/' + draft['id'],
            json={
                'revision': approved['revision'],
                'proposal': proposal,
            },
        )
        assert response.status_code == 422
        assert 'Cấu trúc' in response.json()['detail']
    assert registry.get(draft['id']) == approved


def test_empty_but_structurally_valid_draft_is_saveable(env):
    _, registry, draft = env
    saved = registry.update(
        draft['id'],
        1,
        dict(
            title='',
            expression='',
            unit='',
            variables=[],
            conditions=[],
            test_cases=[],
        ),
    )
    assert saved['status'] == 'pending_review'
    assert saved['validation_errors']


def test_reuploaded_identical_source_reopens_review_without_restoring_approval(env):
    source, registry, draft = env
    approved = approve(registry, draft)
    source_bytes = source.read_bytes()
    registry.invalidate('demo')
    source.unlink()
    stale = registry.get(draft['id'])
    assert stale['status'] == 'stale'
    source.write_bytes(source_bytes)
    assert generate_from_docx(source, 'demo', registry)['created'] == 1
    reopened = registry.get(draft['id'])
    assert reopened['status'] == 'pending_review'
    assert reopened['revision'] > stale['revision'] > approved['revision']
    assert reopened['proposal'] == approved['proposal']
    assert reopened['review'] is None
    assert reopened['history'][-1]['action'] == 'source_restored_for_review'
    assert any(e['action'] == 'approve' for e in reopened['history'])
    with pytest.raises(Conflict):
        registry.compute(reopened['id'], reopened['revision'], {}, {})
    assert generate_from_docx(source, 'demo', registry)['created'] == 0
    assert registry.get(draft['id']) == reopened
    reviewed = registry.decide(
        reopened['id'],
        reopened['revision'],
        'approve',
        'Reviewer 2',
        'Rechecked after restore',
        True,
    )
    assert reviewed['status'] == 'approved'


@pytest.mark.parametrize(
    'expression,expected,passes',
    [
        ('100*a', '1e-12', False),
        ('a', '1e-12', True),
        ('a', '0', False),
        ('a-a', '0', True),
        ('a/3', '3.333333333333333e-13', True),
    ],
)
def test_approval_oracle_scales_to_small_values(env, expression, expected, passes):
    _, registry, draft = env
    proposal = complete_proposal(draft)
    proposal.update(expression=expression, variables=proposal['variables'][:1])
    proposal['test_cases'] = [
        dict(inputs={'a': dict(value='1e-12', unit='Pa')}, expected=expected, unit='Pa')
    ]
    saved = registry.update(draft['id'], draft['revision'], proposal)
    if passes:
        assert (
            registry.decide(saved['id'], saved['revision'], 'approve', 'Reviewer', 'Oracle', True)[
                'status'
            ]
            == 'approved'
        )
    else:
        with pytest.raises(ValueError, match='khớp đáp án'):
            registry.decide(saved['id'], saved['revision'], 'approve', 'Reviewer', 'Oracle', True)
        assert registry.get(saved['id'])['status'] == 'pending_review'
