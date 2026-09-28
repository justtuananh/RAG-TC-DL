"""Bounded Decimal evaluator. No eval, code generation, or arbitrary calls."""
import ast
from decimal import Decimal, InvalidOperation, localcontext
import re

class Invalid(ValueError): pass
UNITS={'Pa':('pressure','1'),'kPa':('pressure','1000'),'MPa':('pressure','1000000'),'bar':('pressure','100000'),
       'mL':('volume','1'),'L':('volume','1000'),'s':('time','1'),'min':('time','60'),
       'Pa.s':('viscosity','1'),'mPa.s':('viscosity','0.001'),'mm/min':('speed','1'),'mm/s':('speed','60'),
       'm/s2':('acceleration','1'),'delta_degC':('temperature_difference','1'),'%':('percent','1')}

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
    def walk(n):
        if isinstance(n,ast.Expression): return walk(n.body)
        if isinstance(n,ast.Name):
            if n.id not in values: raise Invalid('Biến chưa được định nghĩa: '+n.id)
            return values[n.id]
        if isinstance(n,ast.Constant) and type(n.value) in (int,float): return Decimal(str(n.value))
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):
            return -walk(n.operand) if isinstance(n.op,ast.USub) else walk(n.operand)
        if isinstance(n,ast.BinOp):
            a,b=walk(n.left),walk(n.right)
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
        try: result=walk(tree)
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
        n=number(entry.get('value'))
        src=UNITS.get(entry.get('unit')); dst=UNITS.get(v['unit'])
        if not src or not dst or src[0]!=dst[0]: raise Invalid('Đơn vị không tương thích: '+v['key'])
        n=n*Decimal(src[1])/Decimal(dst[1])
        if v.get('min') is not None:
            low=Decimal(str(v['min']))
            if n<low or (v.get('exclusive_min') and n==low): raise Invalid('Ngoài miền giá trị: '+v['key'])
        if v.get('max') is not None and n>Decimal(str(v['max'])): raise Invalid('Ngoài miền giá trị: '+v['key'])
        values[v['key']]=n
    if any(confirmations.get(c) is not True for c in spec.get('conditions',[])):
        raise Invalid('Cần xác nhận đủ điều kiện áp dụng.')
    value=expression(spec['expression'],values)
    return {'status':'ok','value':str(value),'unit':spec['unit'],
            'normalized':{k:str(v) for k,v in values.items()},'expression':spec['expression'],
            'revision':spec['revision'],'formula_id':spec['id']}
