import requests,json
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path('build/formula-review/independent');b='http://127.0.0.1:8081';rows=[]
with sync_playwright() as pw:
 br=pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox']);page=br.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.route('**/api/**',lambda route:route.continue_(url=route.request.url.replace('http://127.0.0.1:5173',b)))
 page.goto('http://127.0.0.1:5173',wait_until='networkidle');page.screenshot(path=str(out/'existing-theme.png'));page.get_by_role('button',name='Tài liệu',exact=True).click();page.get_by_role('button',name='independent.docx',exact=True).click();page.get_by_role('tab',name='Công thức và phê duyệt',exact=True).click();page.get_by_label('Tên công thức',exact=True).wait_for()
 assert page.get_by_role('button',name='Phê duyệt và đăng ký').is_disabled();rows.append('incomplete_approval_disabled')
 page.get_by_label('Tên công thức',exact=True).focus();page.keyboard.press('Tab');assert page.get_by_label('Biểu thức tính',exact=True).evaluate('(e)=>e===document.activeElement');rows.append('keyboard_tab_order')
 page.get_by_label('Tên công thức',exact=True).fill('Đối chứng độc lập áp suất');page.get_by_label('Biểu thức tính',exact=True).fill('(3*a-b)/2');page.get_by_label('Đơn vị kết quả',exact=True).select_option('Pa')
 for n in (1,2):page.get_by_label(f'Ý nghĩa biến {n}',exact=True).fill('Áp suất '+str(n));page.get_by_label(f'Đơn vị biến {n}',exact=True).select_option('Pa')
 page.get_by_label('Điều kiện 1',exact=True).fill('Chỉ thử dữ liệu giả cùng mốc áp suất')
 page.get_by_role('button',name='Thêm ca đối chứng',exact=True).click();page.get_by_label('Ca 1 a',exact=True).fill('7');page.get_by_label('Ca 1 b',exact=True).fill('1');page.get_by_label('Đáp án ca 1',exact=True).fill('10')
 dialogs=[]
 def dismiss(d):dialogs.append(d.message);d.dismiss()
 page.on('dialog',dismiss);page.get_by_role('button',name='Tải lại danh sách',exact=True).click();assert page.get_by_label('Tên công thức',exact=True).input_value()=='Đối chứng độc lập áp suất';assert dialogs;rows.append('unsaved_reload_cancel_preserves');page.remove_listener('dialog',dismiss)
 with page.expect_response(lambda r:r.request.method=='PUT' and '/formula-drafts/' in r.url) as resp:page.get_by_role('button',name='Lưu bản nháp',exact=True).click()
 assert resp.value.status==200 and not resp.value.json()['validation_errors'];rows.append('real_edit_save_api')
 page.get_by_label('Người phê duyệt',exact=True).fill('Đánh giá độc lập dữ liệu giả');page.get_by_label('Nhận xét và căn cứ',exact=True).fill('(3×7−1)/2 = 10 Pa; đáp án cố định trước chạy');page.get_by_role('checkbox',name='Tôi đã đối chiếu biểu thức, biến, đơn vị, điều kiện và đáp án với tài liệu gốc.',exact=True).check()
 with page.expect_response('**/approve') as resp:page.get_by_role('button',name='Phê duyệt và đăng ký').click()
 assert resp.value.status==200;rows.append('real_approve_api')
 page.get_by_label('Tính a',exact=True).fill('1.25');page.get_by_label('Đơn vị tính a',exact=True).select_option('kPa');page.get_by_label('Tính b',exact=True).fill('-250');page.get_by_role('checkbox',name='Chỉ thử dữ liệu giả cùng mốc áp suất',exact=True).check()
 with page.expect_response('**/calculate') as resp:page.get_by_role('button',name='Tính kết quả',exact=True).click()
 assert resp.value.json()['value']=='2000.00';rows.append('real_calculation_2000Pa');page.get_by_text('2000.00 Pa',exact=False).wait_for();page.screenshot(path=str(out/'desktop-review.png'),full_page=True)
 metrics={}
 for name,width,height in [('desktop',1440,1000),('mobile',390,844)]:
  page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(250);metrics[name]=page.evaluate('({scroll:document.documentElement.scrollWidth,width:window.innerWidth,font:getComputedStyle(document.querySelector("input")).fontFamily})');assert metrics[name]['scroll']<=width;page.screenshot(path=str(out/(name+'-viewport.png')),full_page=True)
 rows.append('no_page_horizontal_overflow_desktop_mobile');page.set_viewport_size({'width':1440,'height':1000})
 page.get_by_label('Tính a',exact=True).fill('2');assert page.get_by_text('2000.00 Pa',exact=False).count()==0;rows.append('changed_input_removes_old_result')
 page.get_by_label('Biểu thức tính',exact=True).fill('a-b');assert page.get_by_role('button',name='Tính kết quả').count()==0
 with page.expect_response(lambda r:r.request.method=='PUT' and '/formula-drafts/' in r.url) as resp:page.get_by_role('button',name='Lưu bản nháp',exact=True).click()
 d=resp.value.json();assert d['status']=='pending_review';rows.append('edit_revokes_approval')
 page.get_by_label('Người phê duyệt',exact=True).fill('Independent');page.get_by_label('Nhận xét và căn cứ',exact=True).fill('Ca đối chứng không khớp sau chỉnh sửa')
 with page.expect_response('**/reject') as resp:page.get_by_role('button',name='Từ chối',exact=True).click()
 assert resp.value.status==200 and resp.value.json()['status']=='rejected';rows.append('real_reject_api');assert not errors; br.close()
(out/'browser-results.json').write_text(json.dumps({'checks':rows,'errors':errors,'metrics':metrics},ensure_ascii=False,indent=2));print(json.dumps({'passed':len(rows),'metrics':metrics},ensure_ascii=False))
