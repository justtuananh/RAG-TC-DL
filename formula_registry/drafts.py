"""Extraction produces proposals only; no status transition to approved exists here."""

import ast
import copy
import hashlib
import json
import re
from pathlib import Path

from .store import ROOT, Registry


def simple_expression(latex):
    """Conservative syntax-only suggestion. Units and meaning stay unresolved."""
    if not isinstance(latex, str) or len(latex) > 2000 or latex.count('=') != 1:
        return '', []
    rhs = latex.split('=', 1)[1].strip()

    def group(text, index):
        if index >= len(text) or text[index] != '{':
            raise ValueError()
        level = 1
        end = index + 1
        while end < len(text) and level:
            level += (text[end] == '{') - (text[end] == '}')
            end += 1
        if level:
            raise ValueError()
        return text[index + 1 : end - 1], end

    def translate(text):
        if len(text) > 2000:
            raise ValueError()
        for macro, args in [('\\frac', 2), ('\\sqrt', 1)]:
            while macro in text:
                start = text.index(macro)
                index = start + len(macro)
                values = []
                for _ in range(args):
                    while index < len(text) and text[index].isspace():
                        index += 1
                    value, index = group(text, index)
                    values.append(translate(value))
                value = f'(({values[0]})/({values[1]}))' if args == 2 else f'sqrt({values[0]})'
                text = text[:start] + value + text[index:]
        return text

    try:
        rhs = translate(rhs)
        for source, target in {
            '\\times': '*',
            '\\cdot': '*',
            '×': '*',
            '−': '-',
            '\\rho': 'rho',
            'ρ': 'rho',
            '\\eta': 'eta',
            'η': 'eta',
            '\\tau': 'tau',
            'τ': 'tau',
            '\\Delta': 'delta',
            '∆': 'delta',
            '\\mu': 'mu',
            'μ': 'mu',
            '\\lambda': 'lambda',
            'λ': 'lambda',
        }.items():
            rhs = rhs.replace(source, target)
        rhs = re.sub(r'([A-Za-z][A-Za-z0-9]*)_\{([A-Za-z0-9]+)\}', r'\1_\2', rhs)
        rhs = rhs.replace('^', '**').replace('{', '(').replace('}', ')')
        if '\\' in rhs or len(rhs) > 600:
            raise ValueError()
        symbols = re.findall(r'[A-Za-z][A-Za-z0-9_]*', rhs)
        if len(set(symbols)) != len({symbol.lower() for symbol in symbols}):
            raise ValueError()
        rhs = rhs.lower()
        tree = ast.parse(rhs, mode='eval')
        allowed = (
            ast.Expression,
            ast.BinOp,
            ast.UnaryOp,
            ast.Name,
            ast.Load,
            ast.Constant,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.Pow,
            ast.USub,
            ast.UAdd,
            ast.Call,
        )
        if len(list(ast.walk(tree))) > 120:
            raise ValueError()
        for node in ast.walk(tree):
            if not isinstance(node, allowed):
                raise ValueError()
            if isinstance(node, ast.Call) and (
                not isinstance(node.func, ast.Name)
                or node.func.id != 'sqrt'
                or len(node.args) != 1
                or node.keywords
            ):
                raise ValueError()
            if isinstance(node, ast.Constant) and type(node.value) not in (int, float):
                raise ValueError()
        keys = sorted(
            {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id != 'sqrt'}
        )
        if (
            not keys
            or len(keys) > 12
            or any(not re.fullmatch('[a-z][a-z0-9_]{0,39}', key) for key in keys)
        ):
            raise ValueError()
        return rhs, [dict(key=key, label='', unit='') for key in keys]
    except (ValueError, SyntaxError, RecursionError):
        return '', []


def templates():
    """Existing technically reviewed definitions are suggestions, never user approvals."""
    result = {}
    for folder in [
        ROOT / 'formula_lab/data',
        ROOT / 'formula_lab/data/v2',
        ROOT / 'formula_lab/data/v3',
    ]:
        cards_path = folder / 'sources.json'
        spec_path = folder / 'registry.json'
        if not cards_path.exists() or not spec_path.exists():
            continue
        cards = json.loads(cards_path.read_text())
        specs = json.loads(spec_path.read_text())
        labels = {}
        if (folder / 'conditions.json').exists():
            labels = json.loads((folder / 'conditions.json').read_text())
        for card in cards:
            if len(card['formulas']) != 1:
                continue
            spec = specs.get(card['id'])
            if not spec:
                continue
            result[(card['docx_sha256'], card['formulas'][0]['fid'])] = (card, spec, labels)
    return result


def register_extraction(source_path, document_id, source_hash, entry, markdown, registry=None):
    if Path(source_path).suffix.lower() != '.docx':
        return {
            'created': 0,
            'supported': False,
            'message': 'Hiện tạo bản nháp tự động từ DOCX; PDF chưa có định vị công thức để duyệt.',
        }
    known = templates()
    candidates = []
    formulas = list(entry.get('formula_detail', []))
    # Previously reviewed prose rules may be proposed only for their exact source hash.
    # This does not infer new rules from arbitrary prose or transfer their approval.
    for (sha, _fid), (card, _spec, _labels) in known.items():
        if sha == source_hash and card['formulas'][0]['kind'] == 'prose-rule':
            formulas.append(
                dict(card['formulas'][0], section=card['section'], context=card['context'])
            )
    for formula in formulas:
        latex = formula.get('latex') or ''
        # Standalone symbols are not calculators; failed extraction still gets an incomplete draft.
        if latex and '=' not in latex:
            continue
        fid = formula['fid']
        template = known.get((source_hash, fid))
        warnings = [
            'Bản nháp chưa được người dùng phê duyệt. Cần đối chiếu nguồn và bổ sung ca tính đối chứng.'
        ]
        if template:
            card, spec, labels = template
            proposal = {
                key: copy.deepcopy(spec[key])
                for key in ('title', 'expression', 'unit', 'variables')
            }
            proposal['conditions'] = [
                dict(key=key, label=labels.get(key, '')) for key in spec.get('conditions', [])
            ]
            warnings.append(
                'Gợi ý từ định nghĩa đã đối chiếu kỹ thuật cho đúng hash tài liệu; không kế thừa phê duyệt.'
            )
            if formula.get('kind') == 'prose-rule':
                warnings.append(
                    'Quy tắc định lượng từ lời văn; Pxxx là mã lab, không phải số phương trình in trong nguồn.'
                )
        else:
            expression, variables = simple_expression(latex)
            proposal = dict(
                title=f'{fid} — {formula.get("section") or Path(source_path).stem}',
                expression=expression,
                unit='',
                variables=variables,
                conditions=[dict(key='applicability', label='')],
            )
            warnings.append(
                'Gợi ý cú pháp chưa xác định ý nghĩa biến, đơn vị hay điều kiện áp dụng.'
            )
            if not expression:
                warnings.append(
                    'Chưa chuyển được biểu thức thực thi; người rà soát cần điền hoặc từ chối.'
                )
        if not proposal['conditions']:
            proposal['conditions'] = [dict(key='applicability', label='')]
        proposal['test_cases'] = []
        context = formula.get('context', '')
        if not context:
            at = markdown.find(latex) if latex else -1
            context = markdown[max(0, at - 700) : at + len(latex) + 1200] if at >= 0 else ''
        candidates.append(
            dict(
                source=dict(
                    fid=fid,
                    kind=formula.get('kind', 'unknown'),
                    latex=latex,
                    section=formula.get('section', ''),
                    context=context,
                ),
                proposal=proposal,
                warnings=warnings,
            )
        )
    created = (registry or Registry()).add(source_path, document_id, source_hash, candidates)
    return {'created': created, 'candidates': len(candidates), 'supported': True}


def generate_from_docx(source_path, document_id, registry=None):
    """Backfill already-uploaded files without re-embedding or changing extraction artifacts."""
    import tempfile

    from ingestion.spike_a import _safe, process_one

    source_path = Path(source_path)
    if source_path.suffix.lower() != '.docx':
        raise ValueError('Tạo bản nháp hiện hỗ trợ DOCX; PDF chưa được hỗ trợ.')
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='formula-drafts-') as temp:
        entry = process_one(source_path, Path(temp))
        markdown = (Path(temp) / (_safe(source_path.stem) + '.md')).read_text()
        return register_extraction(source_path, document_id, source_hash, entry, markdown, registry)
