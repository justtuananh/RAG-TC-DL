"""Independent oracle and inputs. Does not import registry, engine, or catalog.
Raw-moment slope (oracle) vs centered covariance (runtime); math.hypot/sqrt
(double) vs Decimal.sqrt runtime. Comparison uses a stated numerical tolerance.
"""
import math
import random

BASE={
1: {'rho':('1000','kg/m3'),'g':('9.8','m/s2'),'h':('0.2','m')},
5: {'bias':('-3','Pa'),'u':('2','Pa')},
6: {'a':('-1','Pa'),'b':('2','1'),'x':('5','Pa')},
7: {'readings':(['10','20','30'],'Pa')},
9: {'xs':(['1','2','3'],'Pa'),'ys':(['3','5','7'],'Pa')},
10: {'y_mean':('5','Pa'),'b':('2','1'),'x_mean':('2','Pa')},
16: {'u':('12','Pa'),'k':('2','1')},
17: {'u':('8','Pa'),'k':('2','1')},
18: {'drift':('3','Pa')},
19: {'u_ch1':('3','Pa'),'u_amb':('4','Pa'),'u_stability':('12','Pa')},
22: {'p':('1000','Pa'),'area':('0.002','m2'),'ua':('0.000004','m2'),'k':('2','1')},
24: {'p':('1000','Pa'),'ulambda':('0.000002','1/Pa'),'k':('2','1')},
26: {'p':('1000','Pa'),'mass':('10','kg'),'um':('0.02','kg'),'k':('2','1')},
31: {'rho':('1000','kg/m3'),'g':('9.8','m/s2'),'uh':('0.001','m'),'k':('2','1')},
33: {'components':(['1','-2','3','4','5','6','7','8','9','10'],'Pa')},
34: {'r':('6','Pa')},35: {'r':('3','Pa')},
36: {f'x{i}':(str(x),'Pa') for i,x in enumerate([1,3,2,-3,4,5],1)},
37: {'f0':('6','Pa')},
50: {'k':('2','1'),'uc':('4','Pa')},
}
# Explicit regression anchors, not generated from either implementation.
ANCHORS={1:1960,5:5,6:9,7:20,9:2,10:1,16:6,17:4,18:1.7320508075688772,
19:13,22:1,24:-1,26:1,31:4.9,33:19.621416870348583,34:2.449489742783178,35:1.7320508075688772,36:5,37:1.7320508075688772,50:8}

def oracle(n,x):
    if n==1:return x['h']*x['rho']*x['g']
    if n==5:return max(x['bias'],-x['bias'])+x['u']
    if n==6:return x['b']*x['x']+x['a']
    if n==7:return math.fsum(x['readings'])/len(x['readings'])
    if n==9:
        xs,ys=x['xs'],x['ys'];count=len(xs)
        return (count*math.fsum(a*b for a,b in zip(xs,ys))-math.fsum(xs)*math.fsum(ys))/(count*math.fsum(a*a for a in xs)-math.fsum(xs)**2)
    if n==10:return -(x['b']*x['x_mean']-x['y_mean'])
    if n in (16,17):return x['u']/x['k']
    if n==18:return x['drift']/math.sqrt(3)
    if n==19:return math.hypot(x['u_ch1'],x['u_amb'],x['u_stability'])
    if n==22:return x['p']*(x['ua']/x['area'])/x['k']
    if n==24:return -(x['ulambda']/x['k'])*x['p']*x['p']
    if n==26:return x['p']*(x['um']/x['mass'])/x['k']
    if n==31:return x['g']*x['rho']*(x['uh']/x['k'])
    if n==33:return math.hypot(*x['components'])
    if n==34:return x['r']/math.sqrt(6)
    if n==35:return x['r']/math.sqrt(3)
    if n==36:return sorted([abs(x['x1']-x['x2']),abs(x['x3']-x['x4']),abs(x['x5']-x['x6'])])[-1]
    if n==37:return (x['f0']/2)/math.sqrt(3)
    if n==50:return x['uc']*x['k']
    raise ValueError(n)

# Natural-language cases authored separately from runtime aliases; no formula ID in queries.
DEV={1:'DPI 610: bù áp suất cột chất lỏng',4:'DPI 610: độ lệch trung bình',5:'DPI 610: sai số cộng độ không đảm bảo',6:'DPI 610: chỉ thị dự đoán',7:'DPI 610: trung bình áp suất chuẩn',9:'DPI 610: hệ số góc hồi quy',10:'DPI 610: hệ số chặn hồi quy',16:'DPI 610: u_ch1',17:'DPI 610: u_amb',18:'DPI 610: độ trôi của chuẩn',19:'DPI 610: tổ hợp chuẩn ba thành phần',22:'DPI 610: độ không đảm bảo diện tích',24:'DPI 610: hệ số giãn nở áp suất',26:'DPI 610: độ không đảm bảo khối lượng',31:'DPI 610: độ không đảm bảo chênh cao',33:'DPI 610: tổng hợp 10 thành phần',34:'DPI 610: độ phân giải tam giác',35:'DPI 610: độ phân giải chữ nhật',36:'DPI 610: độ lệch điểm không',50:'DPI 610: độ không đảm bảo mở rộng'}
HOLDOUT={1:'Theo QTKĐ 1.190, tôi cần hiệu chỉnh cột áp khi chuẩn và máy lệch độ cao.',4:'Tính độ lệch so với áp suất chuẩn theo QTKĐ 1.190 từ nhiều lần đọc.',5:'Cho tôi tính sai số gồm độ lệch và U theo QTKĐ 1.190.',6:'Quan hệ tuyến tính giữa chỉ thị và áp suất chuẩn của DPI610 tính thế nào?',7:'Tôi có các giá trị X; lấy trung bình x theo QTKĐ 1.190 giúp tôi.',9:'Độ dốc hồi quy theo QTKĐ 1.190 được tính từ các cặp đo thế nào?',10:'Tìm tung độ gốc hồi quy theo QTKĐ 1.190.',16:'Tính uch1 theo QTKĐ 1.190, có U và hệ số phủ.',17:'Tính uamb theo QTKĐ 1.190 từ giấy chứng nhận.',18:'Công thức u_stability của QTKĐ 1.190?',19:'Tính u_ch của QTKĐ 1.190 từ ba thành phần chuẩn.',22:'Cho tính u2 theo QTKĐ 1.190.',24:'Cho tính u3 theo QTKĐ 1.190; giữ đúng dấu của nguồn.',26:'Công thức u4 theo QTKĐ 1.190 là gì?',31:'Cho tôi nhập số để tính u9 theo QTKĐ 1.190.',33:'Căn tổng bình phương u1 đến u10 theo QTKĐ 1.190?',34:'QTKĐ 1.190: u_r tam giác với độ phân giải đã xác định.',35:'QTKĐ 1.190: u_r chữ nhật với độ phân giải đã xác định.',36:'QTKĐ 1.190: f0 qua sáu loạt đọc tại điểm 0.',50:'Theo QTKĐ 1.190: độ không đảm bảo đo mở rộng khi đã biết u_c và k.'}

DEV[37]='DPI 610: u_f0'
HOLDOUT[37]='Theo QTKĐ 1.190, tính độ không đảm bảo do độ lệch điểm không từ f0.'

def generate(split):
    rng=random.Random(19007 if split=='dev' else 19083)
    rows=[]
    for n,base in BASE.items():
        for i in range(10):
            inputs={}; values={}
            for key,(raw,unit) in base.items():
                def sample(v):return float(v) if i==0 else float(v)*rng.uniform(.55,1.7)
                x=[sample(t) for t in raw] if isinstance(raw,list) else sample(raw)
                values[key]=x
                value=[format(t,'.15g') for t in x] if isinstance(x,list) else format(x,'.15g')
                # Compute oracle from serialized values to avoid input rounding disagreement.
                values[key]=[float(t) for t in value] if isinstance(value,list) else float(value)
                inputs[key]={'value':value,'unit':unit}
            expected=oracle(n,values)
            if i==0: assert math.isclose(expected,ANCHORS[n],rel_tol=1e-13,abs_tol=1e-13)
            rows.append({'id':f'{split}-F{n:03}-{i:02}', 'formula':f'dpi190_f{n:03}',
                'inputs':inputs,'expected':format(expected,'.17g'),'unit':'1' if n==9 else 'Pa',
                'question':(DEV if split=='dev' else HOLDOUT)[n], 'relative_tolerance':'1e-11','absolute_tolerance':'1e-9'})
    return rows

if __name__=='__main__':
    import hashlib,json
    from pathlib import Path
    out=Path(__file__).resolve().parents[1]/'data/v2'
    hashes={}
    for split in ('dev','holdout'):
        path=out/(split+'-ucs.json'); content=json.dumps(generate(split),ensure_ascii=False,indent=2)+'\n'
        if path.exists() and path.read_text()!=content: raise ValueError('Frozen UC changed; make a new version instead')
        path.write_text(content);hashes[path.name]=hashlib.sha256(content.encode()).hexdigest()
    (out/'UC-FREEZE.json').write_text(json.dumps({'hashes':hashes,'oracle':'independent hand-written math functions, 20 literal anchors','tolerance':'abs <= max(1e-9, abs(gold)*1e-11)','holdout_policy':'Unseen numbers/phrasing within the same 20 formula definitions; not unseen formula families.'},indent=2)+'\n')
    print(hashes)
