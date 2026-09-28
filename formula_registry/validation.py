"""Validate user-edited definitions before they can enter the executable registry."""

import ast
import re
from decimal import Decimal

from formula_lab.engine import UNITS, Invalid, calculate, number

FUNCTIONS = {
    'abs': (1, 1),
    'sqrt': (1, 1),
    'mean': (1, 1),
    'rss': (1, 1),
    'slope': (2, 2),
    'max': (1, 12),
}
KEY = re.compile(r'[a-z][a-z0-9_]{0,39}\Z')


def validate_shape(proposal):
    """Reject malformed containers while allowing semantically incomplete drafts."""

    def require(ok, path):
        if not ok:
            raise ValueError(f'Cấu trúc bản nháp không hợp lệ tại {path}.')

    def strings(value, fields, path):
        require(isinstance(value, dict), path)
        for field in fields:
            require(isinstance(value.get(field), str), f'{path}.{field}')

    strings(proposal, ('title', 'expression', 'unit'), 'proposal')
    for field in ('variables', 'conditions', 'test_cases'):
        require(isinstance(proposal.get(field), list), field)
    for index, variable in enumerate(proposal['variables']):
        path = f'variables[{index}]'
        strings(variable, ('key', 'label', 'unit'), path)
        if 'kind' in variable:
            require(variable['kind'] in ('scalar', 'series'), path + '.kind')
        for key in ('min', 'max'):
            require(
                variable.get(key) is None or type(variable[key]) in (str, int, float),
                path + '.' + key,
            )
        for key in ('exclusive_min', 'exclusive_max'):
            require(key not in variable or type(variable[key]) is bool, path + '.' + key)
        for key in ('min_items', 'max_items'):
            require(key not in variable or type(variable[key]) is int, path + '.' + key)
    for index, condition in enumerate(proposal['conditions']):
        strings(condition, ('key', 'label'), f'conditions[{index}]')
    for index, case in enumerate(proposal['test_cases']):
        path = f'test_cases[{index}]'
        strings(case, ('expected', 'unit'), path)
        require(isinstance(case.get('inputs'), dict), path + '.inputs')
        for key, value in case['inputs'].items():
            input_path = f'{path}.inputs.{key}'
            strings(value, ('unit',), input_path)
            number_value = value.get('value')
            require(
                isinstance(number_value, str)
                or (
                    isinstance(number_value, list) and all(isinstance(n, str) for n in number_value)
                ),
                input_path + '.value',
            )


def executable_spec(proposal, formula_id, revision):
    return dict(
        id=formula_id,
        revision=str(revision),
        title=proposal['title'],
        expression=proposal['expression'],
        unit=proposal['unit'],
        variables=proposal['variables'],
        conditions=[c['key'] for c in proposal['conditions']],
    )


def validate(proposal):
    """Return errors, not exceptions; incomplete drafts are deliberately saveable."""
    errors = []
    if not isinstance(proposal, dict):
        return ['Định nghĩa phải là một object.']
    for field, label in [
        ('title', 'Tên công thức'),
        ('expression', 'Biểu thức'),
        ('unit', 'Đơn vị kết quả'),
    ]:
        if not isinstance(proposal.get(field), str) or not proposal[field].strip():
            errors.append(label + ' chưa được điền.')
    if not isinstance(proposal.get('unit'), str) or proposal['unit'] not in UNITS:
        errors.append('Đơn vị kết quả chưa được hỗ trợ.')
    variables = proposal.get('variables')
    if not isinstance(variables, list) or not 1 <= len(variables) <= 12:
        return errors + ['Cần từ 1 đến 12 biến đầu vào.']
    keys = set()
    for v in variables:
        if not isinstance(v, dict):
            errors.append('Mỗi biến phải là một object.')
            continue
        key = v.get('key')
        if not isinstance(key, str) or not KEY.fullmatch(key) or key in keys or key in FUNCTIONS:
            errors.append('Tên biến không hợp lệ hoặc trùng: ' + str(key))
        else:
            keys.add(key)
        if not isinstance(v.get('label'), str) or not v['label'].strip():
            errors.append('Cần giải thích ý nghĩa biến ' + str(key))
        if not isinstance(v.get('unit'), str) or v['unit'] not in UNITS:
            errors.append('Cần chọn đơn vị hợp lệ cho ' + str(key))
        if v.get('kind', 'scalar') not in ('scalar', 'series'):
            errors.append('Loại biến không hợp lệ: ' + str(key))
        for flag in ('exclusive_min', 'exclusive_max'):
            if flag in v and type(v[flag]) is not bool:
                errors.append(flag + ' phải là true/false.')
        try:
            bounds = {k: number(str(v[k])) for k in ('min', 'max') if v.get(k) is not None}
            if (
                'min' in bounds
                and 'max' in bounds
                and (
                    bounds['min'] > bounds['max']
                    or (
                        bounds['min'] == bounds['max']
                        and (v.get('exclusive_min') or v.get('exclusive_max'))
                    )
                )
            ):
                errors.append('Miền giá trị rỗng: ' + str(key))
        except Invalid:
            errors.append('Giới hạn biến không hợp lệ: ' + str(key))
        if v.get('kind') == 'series':
            low, high = v.get('min_items'), v.get('max_items')
            if type(low) is not int or type(high) is not int or not 1 <= low <= high <= 100:
                errors.append('Danh sách cần giới hạn 1–100 phần tử: ' + str(key))
    conditions = proposal.get('conditions')
    if not isinstance(conditions, list) or not 1 <= len(conditions) <= 20:
        errors.append('Cần ít nhất một điều kiện áp dụng có mô tả rõ ràng (tối đa 20).')
    else:
        seen = set()
        for c in conditions:
            if (
                not isinstance(c, dict)
                or not isinstance(c.get('key'), str)
                or not KEY.fullmatch(c['key'])
            ):
                errors.append('Mã điều kiện không hợp lệ.')
            elif c['key'] in seen:
                errors.append('Mã điều kiện bị trùng.')
            else:
                seen.add(c['key'])
            if (
                not isinstance(c, dict)
                or not isinstance(c.get('label'), str)
                or not c['label'].strip()
            ):
                errors.append('Điều kiện áp dụng cần mô tả để người dùng xác nhận.')
    text = proposal.get('expression')
    if isinstance(text, str) and text.strip():
        try:
            if len(text) > 600:
                raise ValueError('Biểu thức tối đa 600 ký tự.')
            tree = ast.parse(text, mode='eval')
            if len(list(ast.walk(tree))) > 120:
                raise ValueError('Biểu thức quá phức tạp.')

            def walk(node):
                if isinstance(node, ast.Expression):
                    walk(node.body)
                elif isinstance(node, ast.Name) and node.id in keys:
                    return
                elif isinstance(node, ast.Constant) and type(node.value) in (int, float):
                    number(ast.get_source_segment(text, node))
                elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
                    walk(node.operand)
                elif isinstance(node, ast.BinOp) and isinstance(
                    node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
                ):
                    walk(node.left)
                    walk(node.right)
                    if isinstance(node.op, ast.Pow):
                        power = ast.literal_eval(node.right)
                        if type(power) not in (int, float) or power != int(power) or abs(power) > 8:
                            raise ValueError('Số mũ phải là số nguyên từ -8 đến 8.')
                elif (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in FUNCTIONS
                    and not node.keywords
                ):
                    low, high = FUNCTIONS[node.func.id]
                    if not low <= len(node.args) <= high:
                        raise ValueError('Số đối số hàm không hợp lệ.')
                    for arg in node.args:
                        walk(arg)
                else:
                    raise ValueError('Biến hoặc phép toán không được hỗ trợ.')

            walk(tree)
        except (SyntaxError, ValueError, TypeError, Invalid) as exc:
            errors.append('Biểu thức chưa hợp lệ: ' + str(exc))
    cases = proposal.get('test_cases')
    if not isinstance(cases, list) or not 1 <= len(cases) <= 10:
        errors.append('Cần 1–10 ca đối chứng có đầu vào và đáp án do người rà soát xác nhận.')
    elif not errors:
        spec = executable_spec(proposal, 'review-test', 0)
        for index, case in enumerate(cases, 1):
            try:
                if not isinstance(case, dict) or case.get('unit') != spec['unit']:
                    raise Invalid('Đơn vị đáp án phải khớp đơn vị kết quả.')
                expected = number(case.get('expected'))
                result = calculate(
                    spec, case.get('inputs'), dict.fromkeys(spec['conditions'], True)
                )
                # No unit-independent absolute floor; a zero oracle requires zero.
                tolerance = abs(expected) * Decimal('1e-9')
                if abs(Decimal(result['value']) - expected) > tolerance:
                    raise Invalid('Kết quả không khớp đáp án đối chứng.')
            except (Invalid, ValueError, KeyError, TypeError, ArithmeticError) as exc:
                errors.append(f'Ca đối chứng {index}: {exc}')
    return errors
