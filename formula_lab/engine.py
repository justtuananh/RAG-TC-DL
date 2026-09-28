"""Bounded Decimal evaluator. No eval, code generation, or arbitrary calls."""
import ast
from decimal import Decimal, InvalidOperation, localcontext
import re

class Invalid(ValueError): pass
UNITS={'Pa':('pressure','1'),'kPa':('pressure','1000'),'MPa':('pressure','1000000'),'bar':('pressure','100000'),
       'mL':('volume','1'),'L':('volume','1000'),'s':('time','1'),'min':('time','60'),
       'Pa.s':('viscosity','1'),'mPa.s':('viscosity','0.001'),'mm/min':('speed','1'),'mm/s':('speed','60'),
       'm/s2':('acceleration','1'),'delta_degC':('temperature_difference','1'),'%':('percent','1')}
UNITS.update({'1':('dimensionless','1'), 'kg/m3':('density','1'),
              'm':('length','1'), 'mm':('length','0.001'),
              'm2':('area','1'), 'mm2':('area','0.000001'),
              'kg':('mass','1'), 'g':('mass','0.001'),
              '1/Pa':('inverse_pressure','1'), '1/bar':('inverse_pressure','0.00001')})

def number(raw):
    if not isinstance(raw,str) or len(raw)>60 or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d{1,3})?',raw.strip()):
        raise Invalid('Nhập số với dấu chấm thập phân, không dùng dấu phân cách hàng nghìn.')
    try: n=Decimal(raw.strip())
    except InvalidOperation: raise Invalid('Số không hợp lệ.')
    if not n.is_finite() or abs(n)>Decimal('1e30'): raise Invalid('Giá trị không hữu hạn hoặc quá lớn.')
    return n

def expression(text,values):
    if len(text)>600: raise Invalid('Biểu thức quá dài.')
    try: tree=ast.parse(text,mode='eval')
    except SyntaxError: raise Invalid('Biểu thức không hợp lệ.')
    if len(list(ast.walk(tree)))>120: raise Invalid('Biểu thức quá phức tạp.')
    def scalar(value):
        if not isinstance(value,Decimal): raise Invalid('Phép toán này yêu cầu một số.')
        return value
    def series(value):
        if not isinstance(value,list) or not 1<=len(value)<=100: raise Invalid('Danh sách cần từ 1 đến 100 số.')
        return [scalar(x) for x in value]
    def call(name,args):
        if name in ('sqrt','abs') and len(args)==1:
            x=scalar(args[0])
            if name=='abs': return abs(x)
            if x<0: raise Invalid('Không lấy căn bậc hai của số âm.')
            return x.sqrt()
        if name=='max' and 1<=len(args)<=12: return max(scalar(x) for x in args)
        if name in ('mean','rss') and len(args)==1:
            xs=series(args[0])
            return sum(xs)/len(xs) if name=='mean' else sum(x*x for x in xs).sqrt()
        if name=='slope' and len(args)==2:
            xs,ys=map(series,args)
            if len(xs)!=len(ys) or len(xs)<2: raise Invalid('Cần ít nhất hai cặp X/Y, cùng số phần tử.')
            xm,ym=sum(xs)/len(xs),sum(ys)/len(ys)
            den=sum((x-xm)**2 for x in xs)
            if den==0: raise Invalid('Các X trùng nhau; không xác định được hệ số góc.')
            return sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/den
        raise Invalid('Hàm hoặc số đối số không được hỗ trợ.')
    def walk(n):
        if isinstance(n,ast.Expression): return walk(n.body)
        if isinstance(n,ast.Name):
            if n.id not in values: raise Invalid('Biến chưa được định nghĩa: '+n.id)
            return values[n.id]
        if isinstance(n,ast.Constant) and type(n.value) in (int,float): return number(ast.get_source_segment(text,n))
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):
            x=scalar(walk(n.operand))
            return -x if isinstance(n.op,ast.USub) else x
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and not n.keywords:
            return call(n.func.id,[walk(x) for x in n.args])
        if isinstance(n,ast.BinOp):
            a,b=scalar(walk(n.left)),scalar(walk(n.right))
            if isinstance(n.op,ast.Add): return a+b
            if isinstance(n.op,ast.Sub): return a-b
            if isinstance(n.op,ast.Mult): return a*b
            if isinstance(n.op,ast.Div):
                if b==0: raise Invalid('Mẫu số bằng 0.')
                return a/b
            if isinstance(n.op,ast.Pow) and b==int(b) and abs(b)<=8: return a**int(b)
        raise Invalid('Phép toán không được hỗ trợ.')
    with localcontext() as ctx:
        ctx.prec=34
        try: result=scalar(walk(tree))
        except (ArithmeticError,ValueError) as e: raise Invalid('Không tính được trong miền số cho phép.') from e
    if not result.is_finite() or abs(result)>Decimal('1e40'): raise Invalid('Kết quả ngoài miền số cho phép.')
    return result

def calculate(spec,inputs,confirmations):
    if not isinstance(inputs,dict) or not isinstance(confirmations,dict): raise Invalid('Dữ liệu không hợp lệ.')
    expected={v['key'] for v in spec['variables']}
    if set(inputs)!=expected: raise Invalid('Thiếu hoặc thừa biến đầu vào.')
    values={}
    for v in spec['variables']:
        entry=inputs[v['key']]
        if not isinstance(entry,dict): raise Invalid('Thiếu giá trị hoặc đơn vị.')
        if not isinstance(entry.get('unit'),str): raise Invalid('Đơn vị phải là chuỗi ký tự.')
        src=UNITS.get(entry.get('unit')); dst=UNITS.get(v['unit'])
        if not src or not dst or src[0]!=dst[0]: raise Invalid('Đơn vị không tương thích: '+v['key'])
        raw=entry.get('value')
        is_series=v.get('kind')=='series'
        if is_series and (not isinstance(raw,list) or not v.get('min_items',1)<=len(raw)<=v.get('max_items',100)):
            raise Invalid('Số phần tử không hợp lệ: '+v['key'])
        normalized=[]
        for item in raw if is_series else [raw]:
            n=number(item)
            with localcontext() as ctx:
                ctx.prec=34
                n=n*Decimal(src[1])/Decimal(dst[1])
            if v.get('min') is not None:
                low=Decimal(str(v['min']))
                if n<low or (v.get('exclusive_min') and n==low): raise Invalid('Ngoài miền giá trị: '+v['key'])
            if v.get('max') is not None:
                high=Decimal(str(v['max']))
                if n>high or (v.get('exclusive_max') and n==high): raise Invalid('Ngoài miền giá trị: '+v['key'])
            normalized.append(n)
        values[v['key']]=normalized if is_series else normalized[0]
    if any(confirmations.get(c) is not True for c in spec.get('conditions',[])):
        raise Invalid('Cần xác nhận đủ điều kiện áp dụng.')
    value=expression(spec['expression'],values)
    return {'status':'ok','value':str(value),'unit':spec['unit'],
            'normalized':{k:[str(x) for x in v] if isinstance(v,list) else str(v) for k,v in values.items()},'expression':spec['expression'],
            'revision':spec['revision'],'formula_id':spec['id']}
