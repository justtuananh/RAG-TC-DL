import json,hashlib,copy
from pathlib import Path
out=Path('build/formula-review/independent');round1=json.loads((out/'round1.json').read_text());r=copy.deepcopy(round1);r['round']=2
fixes={'C02':'React/API thật rerun10/10 checkpoints. Shape15 loại sai bị422 trước ghi; legacy record sai hiện lỗi dễ hiểu, không crash.','C06':'F02 đã sửa và tự kiểm API approved→delete→samebytesrestore→pending/no review→compute409→reapprove→22Pa; generate tiếp created0 giữ approved/revision. Nguồnhash/địnhvị/chặnđổi/xóa và idempotency tests đều qua.','C08':'Ma trận15 malformed payload422 và không mutation; legacyUI safeerror1/1.20/20 arithmetic/security/domain block; đổiinput xóa kếtquả.','C10':'Rerun UI10/10: save/approve/calculate/reject, dirty reloadcancel giữbản sửa, keyboardTab và responsive. Legacyrecord sai hiệnalert+reload thayvì trắngapp.','C15':'Tự chạy bộ liên quan cuối472/472 BE,47/47 FE; typecheck/lint/build qua. Compose parse/mount/import đã kiểm, chưa Docker runtime vì thiếuCLI; legacy full tests/unit còn2collectionerrors do thiếuGradio.'}
for item in r['criteria']:
 if item['id'] in fixes:item.update(status='Đạt',score=item['weight'],evidence=fixes[item['id']])
r.update(score=sum(x['score'] for x in r['criteria']),critical_all_pass=True,accepted=True,critical_finding=None,business_readiness=False,fe_tests={'passed':47,'total':47},be_relevant_tests={'passed':472,'total':472},regressions={'shape':{'passed':16,'total':16},'restored_source':True})
for rnd in [round1,r]:
 be=[x for x in rnd['criteria'] if int(x['id'][1:])<=9];fe=[x for x in rnd['criteria'] if x['id'] in ['C02','C10','C11','C12']];rnd['technical_subset_scores']={'BE_C01_C09':{'earned':sum(x['score'] for x in be),'weight':63,'percentage':100*sum(x['score'] for x in be)/63},'FE_C02_C10_C12':{'earned':sum(x['score'] for x in fe),'weight':22,'percentage':100*sum(x['score'] for x in fe)/22}}
(out/'round1.json').write_text(json.dumps(round1,ensure_ascii=False,indent=2));(out/'round2.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
files=list(json.loads((out/'snapshot-round1.json').read_text()))+['docs/FORMULA_REVIEW_CRITERIA.md','docs/FORMULA_DRAFT_APPROVAL.md','build/formula-review/independent/numerical_cases.json']
(out/'snapshot-round2.json').write_text(json.dumps({p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files},indent=2));(out/'review-summary.json').write_text(json.dumps({'rounds':[round1,r]},ensure_ascii=False,indent=2))
path=Path('build/formula-review/INDEPENDENT_REVIEW.md');old=path.read_text();Path(out/'report-round1.md').write_text(old)
head='''# Đánh giá độc lập công thức — kết quả sau sửa

**Vòng 1:83/100 → vòng 2:96/100.** Vòng 2 vượt95 và toàn bộ C01–C09 đạt trong phạm vi đã kiểm. **Đạt tiêu chí kỹ thuật vòng này; chưa sẵn sàng nghiệp vụ** vì C16=0/4: thiếu xác thực/phân quyền người duyệt, chuyên gia duyệt nguồn thật và tập đánh giá nghiệp vụ độc lập. Không thay trọng số hoặc nới ngưỡng để đạt điểm.

Hai lỗi đã được gửi dev và sửa: F01 API lưu cấu trúc sai làm trắng toànReact; F02 xóa rồi phục hồi cùng nguồn bị kẹt stale. Reviewer không sửa mã triển khai. Bằng chứng trước/sau và snapshot hashes được giữ riêng.

## Điểm vòng 2

| Mã | Trọng số | Kết quả | Điểm | Bằng chứng mới / giới hạn |
|---|---:|---|---:|---|
'''
for x in r['criteria']:head+=f"| {x['id']} | {x['weight']} | {x['status']} | {x['score']:g} | {x['evidence']} |\n"
head+='''
## Kiểm tra lại độc lập

- **F01:16/16 checks.** 15 biến thể container/nested field sai trả422 và không thay proposal/revision. Một bản ghi lỗi cũ được đặt trực tiếp vào SQLite giả: Chromium hiển thị alert tiếngViệt, nút tải lại hoạt động, khôngpageerror. Không đưa dữ liệu sai vàoDB thật.
- **F02:đạt.** API thật từ approved→xóa→upload đúngbytes/docid→tạo lại: pending revisionmới, xóa currentreview/approval, giữproposal/history; chưa duyệt lại tính409. Duyệt lại rõ ràng mới tính22Pa; tạo lại tiếp không làm mấtapproval. `restore-round2.json` lưu cả trước/sau.
- **472/472 BE tests liên quan;47/47 FE tests;10/10 checkpoints Chromium thật**, TypeScript/lint/build qua. Bundle>500kB còn cảnh báo. Không tuyên bố toànrepo xanh: full legacy tests/unit bị thiếuGradio khicollection; Docker container chưa chạy.
- **Số học:13/14 bằng chính xác;14/14 sau phân tích làm tròn** (slope sai khác1e−33, tolerance tuyệt đối1e−30 được nêu hậu kiểm, không định trước).20/20 ca chặn và6/6 vòngđời riêng. Không che kết quả39/40 exactpass ban đầu. Mẫu không chứng minh đúng mọi công thức hay độ ổn định số trên toànmiền.
- Điểm nhóm theo chính trọng số đã chốt: BE C01–C09 từ52,5/63 (**83,33%**) lên63/63 (**100% mẫu kỹ thuật**); FE C02+C10–C12 từ16/22 (**72,73%**) lên22/22 (**100% mẫu kỹ thuật**). Các nhóm có giaoC02, không cộng hai tỷ lệ này; không phải độphủ hoặc xácsuất đúng. **Điểm tổng dùng để nghiệmthu vẫn96/100.**
- Bảy nguồn thật giữ334pending,0approved; nguồn/SQLite thật chỉ đọc. Chưa có bằng chứng accuracy nghiệp vụ của334ứngviên;57cóexpression/232thiếuLaTeX không phải sốbộ tính đượcduyệt.

Dữ liệu máy đọc: `independent/round1.json`, `round2.json`, `review-summary.json`; hashes `snapshot-round1.json`/`snapshot-round2.json`. Báo cáo vòng1 nguyênvẹn ở `independent/report-round1.md`. Script/ảnh/log cùng thưmục. Phần lịch sử dưới giữ cách chấm và phát hiện vòng1.

---

'''
path.write_text(head+old)
print(json.dumps({'round1':round1['score'],'round2':r['score'],'accepted_technical':r['accepted'],'business_ready':False}))
