import json,hashlib,datetime
from pathlib import Path
from decimal import Decimal,localcontext
root=Path('/tmp/formula-blind-audit'); rows=[]
def case(id,expr,unit,vars,values,expected,**extra):
 rows.append(dict(id=id,group='numeric',expression=expr,unit=unit,variables=vars,inputs=values,expected=expected,tolerance={'relative':'1e-24','absolute':'0'},**extra))
def var(k,u,series=False):return {'key':k,'label':'Synthetic '+k,'unit':u,**({'kind':'series','min_items':2,'max_items':8} if series else {})}
def inp(v,u):return {'value':v,'unit':u}
x=var('x','1',True)
case('N01','mean(x)','1',[x],{'x':inp(['-11','4','13','22'],'1')},'7')
case('N02','mean(x)','1',[x],{'x':inp(['22','-11','13','4'],'1')},'7',metamorphic='Permutation invariance with N01')
case('N03','rss(x)','1',[x],{'x':inp(['-8','15'],'1')},'17')
case('N04','rss(x)','1',[x],{'x':inp(['-24','45'],'1')},'51',metamorphic='Positive scaling 3 times N03')
case('N05','slope(x,y)','1',[x,var('y','1',True)],{'x':inp(['-3','1','5'],'1'),'y':inp(['-8','4','16'],'1')},'3')
case('N06','slope(x,y)','1',[x,var('y','1',True)],{'x':inp(['10000000000000000000000000000','10000000000000000000000000001','10000000000000000000000000003'],'1'),'y':inp(['0','2','6'],'1')},'2',metamorphic='Linear y=2*(x-offset); offset must not change mathematical slope')
with localcontext() as ctx:ctx.prec=90;third=str(Decimal('1e-10')/3)
case('N07','mean(x)','1',[x],{'x':inp(['1e30','1e-10','-1e30'],'1')},third)
case('N08','mean(x)','1',[x],{'x':inp(['1e30','-1e30','1e-10'],'1')},third,metamorphic='Permutation invariance with N07')
case('N09','(a+b)*c','1',[var(k,'1') for k in ['a','b','c']],dict(a=inp('.17','1'),b=inp('.29','1'),c=inp('.125','1')),'0.0575')
case('N10','a**-3','1',[var('a','1')],dict(a=inp('-4','1')),'-0.015625')
case('N11','sqrt(a)','1',[var('a','1')],dict(a=inp('1e-60','1')),'1e-30')
case('N12','a','mm/min',[var('a','mm/min')],dict(a=inp('7.25','mm/s')),'435')
case('N13','a','mPa.s',[var('a','mPa.s')],dict(a=inp('.00037','Pa.s')),'0.37')
case('N14','a','m2',[var('a','m2')],dict(a=inp('1250000','mm2')),'1.25')
case('N15','a','s',[var('a','s')],dict(a=inp('3.5','min')),'210')
case('N16','a-b','mL',[var('a','mL'),var('b','mL')],dict(a=inp('.007','L'),b=inp('3','mL')),'4')
for id,desc,expected in [
('B01','Exclusive minimum 3 kPa: 3000 Pa input must be rejected after conversion',422),
('B02','Inclusive maximum 2 m: 2000 mm must calculate 2 m',200),
('B03','Condition confirmation integer 1 instead of true must be rejected',422),
('B04','Condition confirmation missing one of two required conditions must be rejected',422),
('B05','Nested variable key array must be rejected without revision mutation',422),
('B06','Nested reference input value mixed array string/null must be rejected without mutation',422),
('B07','Revision boolean true must not pass strict integer API schema',422),
('B08','Approval reference incompatible dimensions: a Pa and b m used in a+b with result Pa must be rejected automatically; capability probe, physically invalid',422)]:rows.append(dict(id=id,group='boundary_structure',description=desc,expected_http=expected))
for id,desc in [
('L01','Extraction actual DOCX retains exact file SHA, expression location fid, both sentinel context strings, starts pending with no approval'),
('L02','Approved source bytes changed without registry edit must block calculate409 and public status stale'),
('L03','Reingest same path/document ID A→B→A while B approved must not silently restore approval for old A; all current A definitions pending and compute409'),
('L04','Concurrent same-revision edits yield exactly one success and one409, persisted proposal matches sole winner')]:rows.append(dict(id=id,group='lifecycle',description=desc,expected=True))
for id,desc in [
('U01','Real React synthetic draft loads after real API generate with no browser errors'),
('U02','Unsaved title edit then switch to document source tab: cancel dialog preserves exact title'),
('U03','Remote revision edit then UI saves old revision: error409 shown, local unsaved title retained'),
('U04','Mobile390 viewport no document horizontal overflow; keyboard Tab moves title focus to expression input')]:rows.append(dict(id=id,group='ui',description=desc,expected=True))
manifest=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),protocol='32 locked cases:16 numeric,8 boundary/structure/capability,4 lifecycle,4 real Chromium UI. Each case weight1; group counts reported separately. No quality/capability percentage inferred. Complete-case pass iff every assertion meets manifest; no target95. Numeric abs(actual-expected)<=abs(expected)*1e-24, abs tolerance0. Expected answers from elementary algebra/unit factors and Decimal90 rational oracle, not production engine. Blocked/harness errors remain denominator as unverified; logged separately. One execution, no implementation edits, no post-run tolerance/weight change. Cases release only after result freeze.',cases=rows)
raw=json.dumps(manifest,ensure_ascii=False,indent=2).encode();(root/'manifest.json').write_bytes(raw)
files=list(Path('formula_registry').glob('*.py'))+[Path(x) for x in ['formula_lab/engine.py','api_server.py','ingestion_jobs.py','frontend/src/services/formulaApi.ts','frontend/src/components/docs/FormulaReviewPanel.tsx','frontend/src/components/docs/DocViewerPanel.tsx','frontend/src/store/useAppStore.ts']]
(root/'implementation-before.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2))
seal={'manifest_sha256':hashlib.sha256(raw).hexdigest(),'sealed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'count':len(rows),'groups':{'numeric':16,'boundary_structure':8,'lifecycle':4,'ui':4}};(root/'seal.json').write_text(json.dumps(seal,indent=2));print(json.dumps(seal))
