"""Hand-transcribed technical review for ONE pinned DOCX revision; never auto-approves new sources."""
import hashlib
import json
import re
import zipfile
from pathlib import Path
from lxml import etree
from ingestion.extract_docx import extract_docx

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'formula_lab/data/v2'
REPORT=ROOT/'formula_lab/reports/registry-v2/source-review'
SOURCE='2023. QTKD 1.190 2023 DPI 610 ND 24.01.24.docx'
REVIEWED_SHA='0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab'

def digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def v(key,label,unit='Pa',minimum=None,positive=False,sequence=False,count=None):
    out=dict(key=key,label=label,unit=unit,min=minimum,exclusive_min=positive)
    if sequence: out.update(kind='series',min_items=count or 1,max_items=count or 100)
    return out

def p(key,label): return v(key,label,'Pa',0)
def k(): return v('k','Hệ số phủ k theo chứng nhận','1',0,True)
def arr(key,label,n=1): return v(key,label,sequence=True,count=n if n>2 else None) | {'min_items':n}

def specs():
    # Each tuple: native equation number, title, bounded expression, fields,
    # output unit, explicit conditions, retrieval/routing aliases.
    return [
    (1,'Bù áp suất do chênh cao cột chất lỏng','rho*g*h',[v('rho','Khối lượng riêng môi trường','kg/m3',0,True),v('g','Gia tốc trọng trường','m/s2',0,True),v('h','Chênh cao có dấu theo quy ước','m')],'Pa',['height_sign'],['bù áp suất do chênh cao','bù áp suất cột chất lỏng','hiệu chỉnh cột áp','rho*g*h']),
    (5,'Sai số gồm độ lệch và độ không đảm bảo mở rộng','abs(bias)+u',[v('bias','Độ lệch rho'),p('u','Độ không đảm bảo đo mở rộng U')],'Pa',['expanded_k2'],['sai số gồm độ lệch','sai số cộng độ không đảm bảo','abs(rho)+u']),
    (6,'Chỉ thị dự đoán theo quan hệ tuyến tính','a+b*x',[v('a','Hệ số chặn a'),v('b','Hệ số góc b','1'),v('x','Áp suất chuẩn X')],'Pa',['linear_fit'],['chỉ thị dự đoán','quan hệ tuyến tính','y=a+b*x']),
    (7,'Trung bình các giá trị áp suất chuẩn','mean(readings)',[arr('readings','Các giá trị X_i')],'Pa',['same_series'],['trung bình các giá trị áp suất chuẩn','trung bình áp suất chuẩn','trung bình x']),
    (9,'Hệ số góc hồi quy bình phương tối thiểu','slope(xs,ys)',[arr('xs','Các áp suất chuẩn X_i',2),arr('ys','Các chỉ thị Y_i tương ứng',2)],'1',['paired_readings'],['hệ số góc hồi quy','hệ số b hồi quy','độ dốc hồi quy']),
    (10,'Hệ số chặn hồi quy','y_mean-b*x_mean',[v('y_mean','Trung bình Y'),v('b','Hệ số góc b','1'),v('x_mean','Trung bình X')],'Pa',['linear_fit'],['hệ số chặn hồi quy','hệ số a hồi quy','tung độ gốc hồi quy']),
    (16,'Độ không đảm bảo của áp suất chuẩn u_ch1','u/k',[p('u','U_ch1 từ chứng nhận'),k()],'Pa',['certificate'],['áp suất chuẩn u_ch1','u_ch1','uch1']),
    (17,'Độ không đảm bảo phương tiện đo khí quyển u_amb','u/k',[p('u','U_amb từ chứng nhận'),k()],'Pa',['certificate','absolute_from_gauge'],['phương tiện đo khí quyển','u_amb','uamb']),
    (18,'Độ không đảm bảo do độ ổn định chuẩn','drift/sqrt(3)',[p('drift','Độ trôi driffvalue từ thực nghiệm')],'Pa',['experimental_drift'],['độ không đảm bảo do độ ổn định chuẩn','độ trôi của chuẩn','u_stability']),
    (19,'Độ không đảm bảo liên hợp của tổ hợp chuẩn','sqrt(u_ch1**2+u_amb**2+u_stability**2)',[p('u_ch1','u_ch1'),p('u_amb','u_amb'),p('u_stability','u_stability')],'Pa',['rss_applicable'],['liên hợp của tổ hợp chuẩn','tổ hợp chuẩn ba thành phần','u_ch']),
    (22,'Thành phần độ không đảm bảo do diện tích hiệu dụng u2','p/area*ua/k',[v('p','Áp suất p'),v('area','Diện tích hiệu dụng A_0,c','m2',0,True),v('ua','U_A0,c','m2',0),k()],'Pa',['certificate','piston_standard'],['diện tích hiệu dụng u2','độ không đảm bảo diện tích','u2']),
    (24,'Thành phần có dấu do hệ số giãn nở áp suất u3','-p**2*ulambda/k',[v('p','Áp suất p'),v('ulambda','U_lambda,c','1/Pa',0),k()],'Pa',['certificate','piston_standard','signed_component'],['giãn nở áp suất u3','hệ số giãn nở áp suất','u3']),
    (26,'Thành phần độ không đảm bảo do khối lượng u4','p/mass*um/k',[v('p','Áp suất p'),v('mass','Khối lượng M_c','kg',0,True),v('um','U_Mc','kg',0),k()],'Pa',['certificate','piston_standard'],['khối lượng u4','độ không đảm bảo khối lượng','u4']),
    (31,'Thành phần độ không đảm bảo do chênh cao u9','rho*g*uh/k',[v('rho','Khối lượng riêng chất lỏng','kg/m3',0,True),v('g','Gia tốc trọng trường','m/s2',0,True),v('uh','U_delta_h','m',0)|{'max':'0.002'},k()],'Pa',['piston_standard'],['chênh cao u9','độ không đảm bảo chênh cao','u9']),
    (33,'Tổng hợp mười thành phần chuẩn pít tông','rss(components)',[arr('components','u1 đến u10 theo thứ tự; giữ nguyên dấu',10)],'Pa',['piston_standard','rss_applicable'],['tổng hợp mười thành phần','tổng hợp 10 thành phần','căn tổng bình phương u1']),
    (34,'Độ phân giải theo phân bố tam giác','r/sqrt(6)',[p('r','Độ phân giải r theo loại chỉ thị')],'Pa',['triangular_distribution','resolution_definition'],['độ phân giải theo phân bố tam giác','độ phân giải tam giác','u_r tam giác']),
    (35,'Độ phân giải theo phân bố chữ nhật','r/sqrt(3)',[p('r','Độ phân giải r theo loại chỉ thị')],'Pa',['rectangular_distribution','resolution_definition'],['độ phân giải theo phân bố chữ nhật','độ phân giải chữ nhật','u_r chữ nhật']),
    (36,'Độ lệch điểm không qua ba chu kỳ','max(abs(x2-x1),abs(x4-x3),abs(x6-x5))',[v('x'+str(i),'Chỉ thị tại điểm 0 của loạt M'+str(i)) for i in range(1,7)],'Pa',['zero_cycles'],['độ lệch điểm không','độ lệch zero','f0']),
    (37,'Độ không đảm bảo do độ lệch điểm không u_f0','f0/(2*sqrt(3))',[p('f0','Độ lệch điểm không f0 đã xác định từ M1 đến M6')],'Pa',['zero_shift_reviewed'],['độ không đảm bảo do độ lệch điểm không','u_f0','uf0']),
    (50,'Độ không đảm bảo đo mở rộng U_c','k*uc',[k(),p('uc','Độ không đảm bảo liên hợp đã được xác định')],'Pa',['combined_reviewed'],['độ không đảm bảo đo mở rộng','độ không đảm bảo mở rộng','u_c mở rộng']),
    ]

CONDITIONS={
'height_sign':'Đã đối chiếu quy ước dấu chênh cao với vị trí chuẩn và thiết bị.',
'same_point':'Các chỉ thị thuộc cùng điểm đo và áp suất chuẩn tương ứng.',
'expanded_k2':'U nhập là độ không đảm bảo mở rộng với k=2, P=95% theo mục 5.3.2.',
'linear_fit':'Hệ số và các giá trị trung bình lấy từ cùng bộ dữ liệu, cùng đơn vị áp suất.',
'same_series':'Các giá trị thuộc cùng tập số liệu cần lấy trung bình.',
'paired_readings':'Hai danh sách cùng số phần tử, ghép đúng từng cặp X_i/Y_i và có ít nhất hai X khác nhau.',
'certificate':'U và k lấy từ cùng chứng nhận hiệu chuẩn; không tự mặc định k=2.',
'absolute_from_gauge':'Đang dùng chuẩn áp suất tương đối cùng thiết bị đo khí quyển để kiểm định áp kế tuyệt đối.',
'experimental_drift':'Giá trị độ trôi được xác định từ thực nghiệm phù hợp.',
'rss_applicable':'Đã xác nhận mô hình cộng bình phương này áp dụng, không cần thêm số hạng tương quan.',
'piston_standard':'Chuẩn sử dụng là áp kế pít tông theo mục D.2.2.2.',
'signed_component':'Giữ dấu âm của u3 theo biểu thức nguồn; đây là thành phần có dấu, không phải độ không đảm bảo tổng hợp.',
'resolution_definition':'r đã được xác định đúng theo loại chỉ thị và tình trạng dao động mô tả ở D.2.3.1.',
 'triangular_distribution':'Cơ cấu chỉ thị áp dụng phân bố tam giác.',
 'rectangular_distribution':'Cơ cấu chỉ thị áp dụng phân bố chữ nhật.',
 'zero_cycles':'Sáu giá trị là chỉ thị điểm 0 từ M1 đến M6 đúng thứ tự chu trình tăng/giảm.',
 'zero_shift_reviewed':'f0 đã được xác định đúng theo ba cặp M2-M1, M4-M3, M6-M5 theo D.2.3.2.',
 'combined_reviewed':'u_c đã được xác định bằng mô hình liên hợp được đối chiếu; không tự sử dụng biểu thức F049 còn mâu thuẫn.',
}

def build(draft=False):
    source=ROOT/'TC_DL'/SOURCE
    if hashlib.sha256(source.read_bytes()).hexdigest()!=REVIEWED_SHA: raise ValueError('Source changed: requires a new technical review')
    extracted=extract_docx(str(source))
    with zipfile.ZipFile(source) as z: root=etree.fromstring(z.read('word/document.xml'))
    body=root.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body')
    nodes=root.findall('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath')
    cards=[]; registry={}; review={}
    for n,title,expression,variables,unit,conditions,aliases in specs():
        id=f'dpi190_f{n:03}'; f=extracted.formulas[n-1]; assert f.fid==f'F{n:03}' and f.kind=='omml'
        node=nodes[n-1]; ancestor=node
        while ancestor.getparent() is not body: ancestor=ancestor.getparent()
        index=list(body).index(ancestor)
        context='\n'.join(''.join(e.itertext()) for e in list(body)[max(0,index-2):index+5])
        card=dict(id=id,title=title+' — QTKĐ 1.190 / DPI 610',file=SOURCE,
            stem='2023._QTKD_1.190_2023_DPI_610_ND_24.01.24',section=f.section+' / '+f.fid,
            docx_sha256=REVIEWED_SHA,context=context,formulas=[{'fid':f.fid,'latex':f.latex,'kind':'omml'}],
            revision='2',source_status='technical-reviewed',review_evidence='formula_lab/reports/registry-v2/source-review/REVIEW.md',
            aliases=aliases,technical_review_only=True)
        card['fingerprint']=digest(card)
        spec=dict(id=id,title=card['title'],variables=variables,expression=expression,unit=unit,conditions=conditions,
                  revision='2',source_fingerprint=card['fingerprint'])
        cards.append(card); registry[id]=spec
        review[id]={'card_fingerprint':card['fingerprint'],'spec_sha256':digest(spec),'docx_sha256':REVIEWED_SHA}
        (REPORT/(f.fid+'.xml')).write_bytes(etree.tostring(node,pretty_print=True,encoding='UTF-8'))
    # Review decisions are pinned in version control, never updated by a rebuild.
    approval=DATA/'review_approvals.json'
    if draft:
        return cards,registry,review
    if not approval.exists():
        raise ValueError('Missing signed-off technical review manifest. Generate draft first, review, then pin explicitly.')
    if json.loads(approval.read_text()) != review: raise ValueError('Definition changed: new technical review required')
    for name,data in [('sources',cards),('registry',registry),('conditions',CONDITIONS)]:
        (DATA/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    return cards,registry

if __name__=='__main__': build()
