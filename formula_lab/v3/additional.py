"""Reviewed prose rules and visually checked OLE equations for five more sources."""
import hashlib
import zipfile
from lxml import etree
from ingestion.extract_docx import extract_docx, _load_rels, NS

DOCUMENTS = {
    '1.061': ('QTKD 1.061 2021 ND V2.docx', 'e015e7615952b6aa5b9e48772536adce395efe5409d378dcd2c7412d69e838f5'),
    '1.062': ('QTKD 1.062 2021 ND.docx', 'f848b5ecf6c2efd64e968966e9b285329c23f1db97d8709a7ed2c4c312a85bc3'),
    '1.063': ('QTKD 1.063 2021 BPL.docx', '88a6b7c26022b6985b3cd55392b6dacf8adfc156a46cec7b13dc5e228f09fe15'),
    '1.071': ('QTKD 1.071 2022 FINAL.docx', '7efe8f1f99d82d3dccca6c8197c69415242b4228963d15dc1af33b63ff5291fc'),
    '1.159': ('QTKD 1.159 2021 ND FINAL.docx', '8a86f0df5b45a9cd12a74578ed3fc67aabb0f8315ce43623605ee4f04c3c5eb0'),
}


def build(root, digest, variable):
    positive = lambda key, label, unit='Pa': variable(key, label, unit, min=0, exclusive_min=True)
    # Pxxx is a lab identifier for a prose rule, never an equation number in the source.
    rows = [
        ('1.061', 'P001', 'Áp suất thử độ kín và chịu tải van', '1.5*pmax',
         [positive('pmax', 'Áp suất lớn nhất theo thiết kế')], 'Pa', '6.2.2',
         'ở áp suất bằng 1,5 lần áp suất lớn nhất theo thiết kế', r'P_{test}=1.5P_{max}',
         'Đúng áp suất lớn nhất theo thiết kế tại 6.2.2; chỉ tính mức áp suất thử, không kết luận van đạt.',
         ['áp suất thử độ kín', 'áp suất thử chịu tải']),
        ('1.061', 'P002', 'Độ lớn sai số áp suất chỉnh đặt cho phép', 'max(0.03*pcd,15000)',
         [positive('pcd', 'Áp suất chỉnh đặt')], 'Pa', '6.3.1',
         'không nhỏ hơn ± 0,15 bar', r'E_{max}=\max(0.03P_{cd},15000\,\mathrm{Pa})',
         'Áp dụng giới hạn ±3% nhưng không nhỏ hơn ±0,15 bar tại 6.3.1; kết quả là độ lớn giới hạn, không kết luận đạt.',
         ['sai số áp suất chỉnh đặt cho phép', 'giới hạn sai số van']),
        ('1.062', 'P001', 'Mức áp suất bơm phụ một phần mười', 'pmax/10',
         [positive('pmax', 'Giới hạn áp suất làm việc tối đa')], 'Pa', '5.2.1 / 5.2.2',
         'khả năng tạo áp suất tới 1/10', r'P_{aux}=P_{max}/10',
         'Bàn tạo áp có bơm nén phụ, áp dụng nhánh 5.2.1/5.2.2; không dùng cho bàn không có bơm phụ.',
         ['áp suất bơm phụ một phần mười', 'mức áp suất bơm phụ']),
        ('1.062', 'P002', 'Giới hạn áp suất kiểm tra van bảo vệ bơm phụ', '0.2*pmax',
         [positive('pmax', 'Giới hạn áp suất làm việc tối đa')], 'Pa', '5.2.1',
         'không tăng áp suất vượt quá 20 %', r'P_{limit}=0.2P_{max}',
         'Bàn tạo áp có van an toàn bảo vệ bơm phụ theo 5.2.1; kết quả là giới hạn không được vượt, không phải áp suất bắt buộc phải đạt.',
         ['giới hạn áp suất kiểm tra van bảo vệ bơm phụ', 'giới hạn van bơm phụ']),
        ('1.062', 'P003', 'Giới hạn độ tụt áp sau năm phút', '0.05*pmax',
         [positive('pmax', 'Độ lớn giới hạn áp suất làm việc tối đa')], 'Pa', '5.3',
         'Độ tụt áp sau 5 min không được vượt quá 5%', r'\Delta P_{limit}=0.05P_{max}',
         'Đúng phép thử 5.3 (duy trì 20 min, điều chỉnh lại, đọc sau 5 min); pmax là độ lớn dương, không tự áp dụng cho nhánh tăng áp chân không.',
         ['giới hạn độ tụt áp', 'độ tụt áp cho phép']),
        ('1.063', 'P001', 'Giới hạn độ tụt áp bình phân ly sau năm phút', '0.05*pmax',
         [positive('pmax', 'Giới hạn áp suất làm việc tối đa')], 'Pa', '5.3',
         'Độ tụt áp suất trong bình phân ly trong 5 min không được vượt quá 5%', r'\Delta P_{limit}=0.05P_{max}',
         'Áp dụng phép thử bình phân ly tại 5.3, duy trì 15 min rồi điều chỉnh/đọc sau 5 min và lặp lại; chỉ tính giới hạn.',
         ['giới hạn độ tụt áp bình phân ly', 'giới hạn độ tụt áp', 'độ tụt áp cho phép']),
        ('1.071', 'F013', 'Sai số tuyệt đối trung bình hai lần đo', '((p-pc1)+(p-pc2))/2',
         [positive('p', 'Áp suất danh nghĩa đã hiệu chỉnh', 'bar'),
          variable('pc1', 'Chỉ thị chuẩn lần 1', 'bar', min=0), variable('pc2', 'Chỉ thị chuẩn lần 2', 'bar', min=0)],
         'bar', '5.3', None, None,
         'Hai lần đo cùng điểm H3000, theo hai chiều quay; P đã hiệu chỉnh gia tốc trọng trường nơi đo. Giữ dấu sai số, không lấy trị tuyệt đối.',
         ['sai số tuyệt đối trung bình', 'sai số tuyệt đối']),
        ('1.159', 'F031', 'Áp suất tuyệt đối tại đáy pít tông', 'ps+mu',
         [variable('ps', 'P_s,i đã xác định riêng cho chế độ tuyệt đối', min=0),
          variable('mu', 'Áp suất dư trong buồng chân không tuyệt đối', min=0, max='10', exclusive_max=True)],
         'Pa', '6.3.2', None, None,
         'Chế độ tuyệt đối; P_s,i đã tính riêng, mu là áp suất dư buồng chân không ổn định dưới 10 Pa theo 5.2; kết quả tại đáy pít tông, chưa bù chênh cao.',
         ['áp suất tuyệt đối tại đáy pít tông', 'áp suất tuyệt đối tại đáy', 'p_abs']),
    ]
    latex = {
        '1.071': [('F013', r'\Delta=\frac{\Delta_1+\Delta_2}{2}'),
                  ('F014', r'\Delta_1=P-P_{c1}'), ('F015', r'\Delta_2=P-P_{c2}')],
        '1.159': [('F031', r'P_{abs}=P_{s,i}+\mu')],
    }
    cards, registry, reviews, evidence, conditions = [], {}, {}, {}, {}
    for code, fid, title, expression, variables, unit, section, marker, display, condition, aliases in rows:
        filename, expected = DOCUMENTS[code]
        path = root/'TC_DL'/filename
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Source changed: requires a new technical review')
        id = 'qtkd'+code.replace('1.', '')+'_'+fid.lower()
        condition_id = 'v3_'+id
        conditions[condition_id] = condition
        with zipfile.ZipFile(path) as archive:
            tree = etree.fromstring(archive.read('word/document.xml'))
            body = tree.find('w:body', NS)
            if marker:
                nodes = [p for p in body.findall('w:p', NS) if marker in ''.join(p.itertext())]
                if len(nodes) != 1:
                    raise ValueError('Prose anchor changed or ambiguous: '+id)
                node = nodes[0]
                formulas = [dict(fid=fid, latex=display, kind='prose-rule')]
            else:
                parsed = extract_docx(str(path))
                rels = _load_rels(archive)
                formulas = []
                for equation_id, transcribed in latex[code]:
                    formula = next(f for f in parsed.formulas if f.fid == equation_id)
                    if formula.kind != 'ole' or not formula.img_target or not formula.ole_target:
                        raise ValueError('Expected rendered OLE evidence')
                    formulas.append(dict(fid=equation_id, latex=transcribed, kind='ole'))
                    evidence[id+'_'+equation_id+'.wmf'] = archive.read(formula.img_target)
                    evidence[id+'_'+equation_id+'.bin'] = archive.read(formula.ole_target)
                    if equation_id == fid:
                        node = next(n for n in tree.findall('.//o:OLEObject', NS)
                                    if rels[n.get('{'+NS['r']+'}id')] == formula.ole_target)
                while node.getparent() is not body:
                    node = node.getparent()
            index = list(body).index(node)
            context = '\n'.join(''.join(n.itertext()) for n in list(body)[max(0,index-3):index+12])
            evidence[id+'.xml'] = etree.tostring(node, encoding='UTF-8', pretty_print=True)
        card = dict(id=id, title=title+' — QTKĐ '+code, file=filename,
                    stem=filename[:-5].replace(' ', '_'), procedure=code, section=section+' / '+fid,
                    docx_sha256=expected, context=context, formulas=formulas, revision='3',
                    source_status='technical-reviewed', technical_review_only=True, aliases=aliases,
                    review_evidence='formula_lab/reports/registry-v3/source-review/REVIEW.md')
        if marker:
            card['derivation_note'] = 'Quy tắc chép từ lời văn; Pxxx là mã lab, không phải số công thức nguồn.'
        card['fingerprint'] = digest(card)
        spec = dict(id=id, title=card['title'], expression=expression, variables=variables, unit=unit,
                    conditions=[condition_id], revision='3', source_fingerprint=card['fingerprint'])
        cards.append(card)
        registry[id] = spec
        reviews[id] = dict(card_fingerprint=card['fingerprint'], spec_sha256=digest(spec), docx_sha256=expected,
                           conditions_sha256=digest({condition_id:condition}))
    return cards, registry, reviews, evidence, conditions
