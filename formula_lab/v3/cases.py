"""Public development examples, hand-calculated anchors; not an independent holdout."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]/'data/v3'

# Expected values are written independently of engine/catalog expressions.
ANCHORS = [
    ('qtkd160_f001', 'QTKĐ 1.160: bù áp suất do chênh cao', {'rho':('1000','kg/m3'),'g':('9.8','m/s2'),'h':('-20','mm')}, '-196','Pa'),
    ('qtkd160_f005', 'QTKĐ 1.160: chỉ thị dự đoán', {'a':('-2','Pa'),'b':('1.5','1'),'x':('10','Pa')}, '13','Pa'),
    ('qtkd160_f006', 'QTKĐ 1.160: trung bình áp suất chuẩn', {'readings':(['-3','0','6'],'Pa')}, '1','Pa'),
    ('qtkd160_f007', 'QTKĐ 1.160: trung bình chỉ thị', {'readings':(['2','5','8'],'Pa')}, '5','Pa'),
    ('qtkd160_f008', 'QTKĐ 1.160: hệ số góc hồi quy', {'xs':(['1','2','3'],'Pa'),'ys':(['2','5','8'],'Pa')}, '3','1'),
    ('qtkd160_f009', 'QTKĐ 1.160: hệ số chặn hồi quy', {'y_mean':('5','Pa'),'b':('3','1'),'x_mean':('2','Pa')}, '-1','Pa'),
    ('qtkd160_f033', 'QTKĐ 1.160: độ phân giải tam giác', {'r':('6','Pa')}, '2.449489742783178098197284074705892','Pa'),
    ('qtkd160_f034', 'QTKĐ 1.160: độ phân giải chữ nhật', {'r':('3','Pa')}, '1.732050807568877293527446341505872','Pa'),
    ('dpi190_f008', 'DPI 610: trung bình chỉ thị', {'readings':(['-6','0','3'],'Pa')}, '-1','Pa'),
    ('dpi190_f038', 'DPI 610: độ lặp lại chiều tăng', {'x3_j':('100','Pa'),'x3_0':('3','Pa'),'x1_j':('102','Pa'),'x1_0':('1','Pa')}, '4','Pa'),
    ('dpi190_f039', 'DPI 610: độ lặp lại chiều giảm', {'x4_j':('98','Pa'),'x4_0':('-2','Pa'),'x2_j':('97','Pa'),'x2_0':('1','Pa')}, '4','Pa'),
    ('dpi190_f042', 'DPI 610: độ tái lặp lại chiều tăng', {'x5_j':('-100','Pa'),'x5_0':('-3','Pa'),'x1_j':('-90','Pa'),'x1_0':('-2','Pa')}, '9','Pa'),
    ('dpi190_f043', 'DPI 610: độ tái lặp lại chiều giảm', {'x6_j':('100','Pa'),'x6_0':('5','Pa'),'x2_j':('99','Pa'),'x2_0':('4','Pa')}, '0','Pa'),
    ('qtkd061_p001', 'QTKĐ 1.061: áp suất thử độ kín', {'pmax':('100','bar')}, '15000000','Pa'),
    ('qtkd061_p002', 'QTKĐ 1.061: giới hạn sai số van', {'pcd':('2','bar')}, '15000','Pa'),
    ('qtkd062_p001', 'QTKĐ 1.062: mức áp suất bơm phụ', {'pmax':('100','bar')}, '1000000','Pa'),
    ('qtkd062_p002', 'QTKĐ 1.062: giới hạn van bơm phụ', {'pmax':('100','bar')}, '2000000','Pa'),
    ('qtkd062_p003', 'QTKĐ 1.062: độ tụt áp cho phép', {'pmax':('100','bar')}, '500000','Pa'),
    ('qtkd063_p001', 'QTKĐ 1.063: giới hạn độ tụt áp bình phân ly', {'pmax':('200','bar')}, '1000000','Pa'),
    ('qtkd071_f013', 'H3000: sai số tuyệt đối trung bình', {'p':('100','bar'),'pc1':('101','bar'),'pc2':('103','bar')}, '-2','bar'),
    ('qtkd159_f031', 'QTKĐ 1.159: áp suất tuyệt đối tại đáy', {'ps':('1500','Pa'),'mu':('5','Pa')}, '1505','Pa'),
]


def cases():
    rows = []
    for id, question, inputs, expected, unit in ANCHORS:
        for variant in ('anchor', 'converted_units'):
            values = {}
            for key, (raw, src_unit) in inputs.items():
                target, factor = src_unit, Decimal(1)
                if variant == 'converted_units':
                    if src_unit == 'Pa': target, factor = 'kPa', Decimal('0.001')
                    elif src_unit == 'bar': target, factor = 'MPa', Decimal('0.1')
                    elif src_unit == 'mm': target, factor = 'm', Decimal('0.001')
                convert = lambda value: str(Decimal(value)*factor)
                values[key] = {'value':[convert(x) for x in raw] if isinstance(raw,list) else convert(raw), 'unit':target}
            rows.append(dict(id=id+'/'+variant, formula=id, question=question, inputs=values,
                             expected=expected, unit=unit, absolute_tolerance='1e-12', relative_tolerance='1e-12'))
    return rows


if __name__ == '__main__':
    path = DATA/'dev-ucs.json'
    path.write_text(json.dumps(cases(), ensure_ascii=False, indent=2)+'\n')
    (DATA/'UC-FREEZE.json').write_text(json.dumps({
        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'role':'public_development_regression_not_independent_holdout',
        'questions':21, 'cases':42, 'oracle':'21 manually calculated anchors; each repeated with equivalent input units',
    }, indent=2)+'\n')
