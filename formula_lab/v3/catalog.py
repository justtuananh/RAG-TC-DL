"""21 reviewed additions across seven sources; building never grants approval."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from lxml import etree
from ingestion.extract_docx import extract_docx

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'formula_lab/data/v3'
REPORT = ROOT / 'formula_lab/reports/registry-v3/source-review'
SOURCES = {
    '1.160': ('QTKD 1.160 2021 ND FINAL.docx',
              'd31461da01922c798853b19291d07f076ff6e3b5962f3416e80a7993bcb8a6ed'),
    '1.190': ('2023. QTKD 1.190 2023 DPI 610 ND 24.01.24.docx',
              '0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab'),
}
CONDITIONS = {
    'v3_height_sign': 'Đã đối chiếu quy ước dấu và hai mốc chênh cao trong QTKĐ 1.160 mục 4.2.1.',
    'v3_linear_fit': 'X là áp suất chuẩn, Y là chỉ thị áp kế kiểm; hệ số và số liệu thuộc cùng bộ đo, cùng đơn vị.',
    'v3_same_series': 'Các số đọc thuộc cùng tập X hoặc cùng tập Y được chọn theo phụ lục D; không trộn hai tập.',
    'v3_paired_readings': 'X/Y ghép đúng từng cặp, cùng số phần tử, có ít nhất hai X khác nhau.',
    'v3_triangular': 'Cơ cấu chỉ thị áp dụng phân bố tam giác theo QTKĐ 1.160 mục D.2.3.1.',
    'v3_rectangular': 'Cơ cấu chỉ thị áp dụng phân bố chữ nhật theo QTKĐ 1.160 mục D.2.3.1.',
    'v3_resolution': 'r đã xác định theo loại chỉ thị và dao động tại D.2.3.1; dùng cùng đơn vị áp suất.',
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def variable(key, label, unit='Pa', **bounds):
    return dict(key=key, label=label, unit=unit, **bounds)


def series(key, label, minimum=1):
    return variable(key, label, kind='series', min_items=minimum, max_items=100)


def specs():
    result = [
        ('1.160', 1, 'Bù áp suất do chênh cao cột chất lỏng', 'rho*g*h',
         [variable('rho', 'Khối lượng riêng môi trường', 'kg/m3', min=0, exclusive_min=True),
          variable('g', 'Gia tốc trọng trường', 'm/s2', min=0, exclusive_min=True),
          variable('h', 'Chênh cao có dấu giữa hai mốc', 'm')], 'Pa', ['v3_height_sign'],
         ['bù áp suất do chênh cao', 'bù áp suất cột chất lỏng', 'hiệu chỉnh cột áp']),
        ('1.160', 5, 'Chỉ thị dự đoán theo quan hệ tuyến tính', 'a+b*x',
         [variable('a', 'Hệ số chặn a'), variable('b', 'Hệ số góc b', '1'), variable('x', 'Áp suất chuẩn X')],
         'Pa', ['v3_linear_fit'], ['chỉ thị dự đoán', 'quan hệ tuyến tính', 'y=a+b*x']),
        ('1.160', 6, 'Trung bình các giá trị áp suất chuẩn', 'mean(readings)',
         [series('readings', 'Các giá trị X_i')], 'Pa', ['v3_same_series'],
         ['trung bình các giá trị áp suất chuẩn', 'trung bình áp suất chuẩn', 'trung bình x']),
        ('1.160', 7, 'Trung bình chỉ thị áp kế kiểm', 'mean(readings)',
         [series('readings', 'Các giá trị Y_i')], 'Pa', ['v3_same_series'],
         ['trung bình chỉ thị áp kế kiểm', 'trung bình chỉ thị', 'trung bình y']),
        ('1.160', 8, 'Hệ số góc hồi quy bình phương tối thiểu', 'slope(xs,ys)',
         [series('xs', 'Các áp suất chuẩn X_i', 2), series('ys', 'Các chỉ thị Y_i tương ứng', 2)],
         '1', ['v3_paired_readings'], ['hệ số góc hồi quy', 'hệ số b hồi quy', 'độ dốc hồi quy']),
        ('1.160', 9, 'Hệ số chặn hồi quy', 'y_mean-b*x_mean',
         [variable('y_mean', 'Trung bình Y'), variable('b', 'Hệ số góc b', '1'), variable('x_mean', 'Trung bình X')],
         'Pa', ['v3_linear_fit'], ['hệ số chặn hồi quy', 'hệ số a hồi quy', 'tung độ gốc hồi quy']),
        ('1.160', 33, 'Độ phân giải theo phân bố tam giác', 'r/sqrt(6)',
         [variable('r', 'Độ phân giải r', min=0)], 'Pa', ['v3_triangular', 'v3_resolution'],
         ['độ phân giải theo phân bố tam giác', 'độ phân giải tam giác', 'u_r tam giác']),
        ('1.160', 34, 'Độ phân giải theo phân bố chữ nhật', 'r/sqrt(3)',
         [variable('r', 'Độ phân giải r', min=0)], 'Pa', ['v3_rectangular', 'v3_resolution'],
         ['độ phân giải theo phân bố chữ nhật', 'độ phân giải chữ nhật', 'u_r chữ nhật']),
        ('1.190', 8, 'Trung bình chỉ thị áp kế kiểm', 'mean(readings)',
         [series('readings', 'Các giá trị Y_i')], 'Pa', ['v3_same_series'],
         ['trung bình chỉ thị áp kế kiểm', 'trung bình chỉ thị', 'trung bình y']),
    ]
    for number, name, first, second, section in [
        (38, 'Độ lặp lại chiều tăng', 3, 1, 'D.2.3.3'),
        (39, 'Độ lặp lại chiều giảm', 4, 2, 'D.2.3.3'),
        (42, 'Độ tái lặp lại chiều tăng', 5, 1, 'D.2.3.4'),
        (43, 'Độ tái lặp lại chiều giảm', 6, 2, 'D.2.3.4'),
    ]:
        condition = f'v3_cycles_{first}_{second}'
        result.append(('1.190', number, name,
                       f'abs((x{first}_j-x{first}_0)-(x{second}_j-x{second}_0))',
                       [variable(f'x{i}_{point}', f'Chỉ thị loạt M{i} tại điểm {point}')
                        for i in (first, second) for point in ('j', '0')],
                       'Pa', [condition], [name.lower(), name.lower().replace('lặp lại', 'lặp')]))
    return result


for first, second, section in [(3, 1, 'D.2.3.3'), (4, 2, 'D.2.3.3'), (5, 1, 'D.2.3.4'), (6, 2, 'D.2.3.4')]:
    CONDITIONS[f'v3_cycles_{first}_{second}'] = (
        f'Đúng loạt M{first}/M{second}, cùng điểm áp suất j và chiều đo theo {section} QTKĐ 1.190; '
        'mỗi loạt dùng số đọc điểm 0 của chính loạt đó. Chỉ tính độ lệch từng chiều, chưa suy ra độ không đảm bảo tổng hợp.'
    )


def build(draft=False):
    cards, registry, reviews, evidence = [], {}, {}, {}
    documents = {}
    for procedure, (filename, expected_sha) in SOURCES.items():
        path = ROOT / 'TC_DL' / filename
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
            raise ValueError('Source changed: requires a new technical review')
        parsed = extract_docx(str(path))
        with zipfile.ZipFile(path) as archive:
            tree = etree.fromstring(archive.read('word/document.xml'))
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
              'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math'}
        nodes = tree.findall('.//m:oMath', ns)
        # Ordinal mapping is valid only for these all-OMML pinned documents.
        if len(nodes) != len(parsed.formulas) or any(f.kind != 'omml' for f in parsed.formulas):
            raise ValueError('Unexpected source equation topology')
        documents[procedure] = (parsed, nodes, tree.find('w:body', ns))
    for procedure, number, title, expression, variables, unit, conditions, aliases in specs():
        parsed, nodes, body = documents[procedure]
        formula, node = parsed.formulas[number-1], nodes[number-1]
        fid = f'F{number:03}'
        if formula.fid != fid:
            raise ValueError('Source equation numbering changed')
        ancestor = node
        while ancestor.getparent() is not body:
            ancestor = ancestor.getparent()
        index = list(body).index(ancestor)
        context = '\n'.join(''.join(e.itertext()) for e in list(body)[max(0, index-7):index+8])
        filename, source_sha = SOURCES[procedure]
        id = ('qtkd160_' if procedure == '1.160' else 'dpi190_') + fid.lower()
        card = dict(id=id, title=title+' — QTKĐ '+procedure, file=filename,
                    stem=filename[:-5].replace(' ', '_'), section=formula.section+' / '+fid,
                    procedure=procedure, docx_sha256=source_sha, context=context,
                    formulas=[dict(fid=fid, latex=formula.latex, kind='omml')], revision='3',
                    source_status='technical-reviewed', technical_review_only=True, aliases=aliases,
                    review_evidence='formula_lab/reports/registry-v3/source-review/REVIEW.md')
        card['fingerprint'] = digest(card)
        spec = dict(id=id, title=card['title'], variables=variables, expression=expression,
                    unit=unit, conditions=conditions, revision='3', source_fingerprint=card['fingerprint'])
        cards.append(card)
        registry[id] = spec
        reviews[id] = dict(card_fingerprint=card['fingerprint'], spec_sha256=digest(spec),
                           docx_sha256=source_sha,
                           conditions_sha256=digest({key: CONDITIONS[key] for key in conditions}))
        evidence[id+'.xml'] = etree.tostring(node, pretty_print=True, encoding='UTF-8')
    from .additional import build as build_additional
    extra_cards, extra_specs, extra_reviews, extra_evidence, extra_conditions = build_additional(ROOT, digest, variable)
    cards.extend(extra_cards)
    registry.update(extra_specs)
    reviews.update(extra_reviews)
    evidence.update(extra_evidence)
    all_conditions = CONDITIONS | extra_conditions
    if draft:
        return cards, registry, reviews, evidence
    pinned = DATA / 'review_approvals.json'
    if not pinned.exists() or json.loads(pinned.read_text()) != reviews:
        raise ValueError('Definition changed or missing technical review; inspect draft before pinning')
    # No files are modified until every source and definition has passed review checks.
    DATA.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    for filename, content in evidence.items():
        (REPORT / filename).write_bytes(content)
    for name, value in [('sources', cards), ('registry', registry), ('conditions', all_conditions)]:
        (DATA / (name+'.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    return cards, registry


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--draft', action='store_true', help='Print review fingerprints without writing files')
    args = parser.parse_args()
    result = build(draft=args.draft)
    if args.draft:
        print(json.dumps(result[2], ensure_ascii=False, indent=2))
