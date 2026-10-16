"""Deliberately small safe evaluator for display arithmetic equalities."""

from __future__ import annotations

import ast
import re
from decimal import Decimal, InvalidOperation


class ArithmeticError(ValueError):
    """The expression uses unsupported or invalid arithmetic."""


_RESULT_UNITS = r"\s*(km/h|m/s|work/day|km|m|days?|meters?|metres?|rs|lakh|%)\s*$"


def _value(node: ast.AST) -> Decimal:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return Decimal(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _value(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
        left, right = _value(node.left), _value(node.right)
        if isinstance(node.op, ast.Add): return left + right
        if isinstance(node.op, ast.Sub): return left - right
        if isinstance(node.op, ast.Mult): return left * right
        if isinstance(node.op, ast.Div):
            if right == 0: raise ArithmeticError("division by zero")
            return left / right
        if right != int(right) or abs(int(right)) > 12: raise ArithmeticError("unsupported exponent")
        return left ** int(right)
    raise ArithmeticError("unsupported expression")


def _evaluate_clean(expression: str) -> Decimal:
    sanitized = expression.replace("\u00d7", "*").replace("\u00f7", "/").strip()
    sanitized = re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", "*", sanitized)
    sanitized = re.sub(r"(?<![\w.])(\d+(?:\.\d+)?)%", r"(\1 / 100)", sanitized)
    try:
        return _value(ast.parse(sanitized, mode="eval").body)
    except (SyntaxError, InvalidOperation) as exc:
        raise ArithmeticError("invalid arithmetic") from exc


def _strip_result_unit(expression: str) -> str:
    return re.sub(_RESULT_UNITS, "", expression, flags=re.I)


def evaluate(expression: str) -> Decimal:
    return _evaluate_clean(expression)


def equation_result(line: str) -> Decimal | None:
    """Return the verified right-hand result, or None for non-equations."""
    if verify_line(line) is not True:
        return None
    _, right = (part.strip() for part in line.split("=", 1))
    try:
        return _evaluate_clean(_strip_result_unit(right))
    except ArithmeticError:
        return None


def equation_operands(line: str) -> tuple[Decimal, ...] | None:
    """Return numeric operands from the left side of a valid equality."""
    if line.count("=") != 1 or verify_line(line) is not True:
        return None
    left = line.split("=", 1)[0].strip()
    sanitized = left.replace("\u00d7", "*").replace("\u00f7", "/")
    sanitized = re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", "*", sanitized)
    try:
        expression = ast.parse(sanitized, mode="eval").body
    except SyntaxError:
        return None
    operands: list[Decimal] = []
    for node in ast.walk(expression):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            operands.append(Decimal(str(node.value)))
    return tuple(operands)


def equation_has_computation(line: str) -> bool:
    """Return whether the left side performs an arithmetic operation."""
    if line.count("=") != 1:
        return False
    left = line.split("=", 1)[0].strip()
    sanitized = left.replace("\u00d7", "*").replace("\u00f7", "/")
    sanitized = re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", "*", sanitized)
    try:
        expression = ast.parse(sanitized, mode="eval").body
    except SyntaxError:
        return False
    return any(isinstance(node, ast.BinOp) for node in ast.walk(expression))


def numeric_answer(value: str) -> Decimal | None:
    """Extract a numeric answer while ignoring its display unit or percent sign."""
    cleaned = value.replace(",", "").strip()
    match = re.match(
        r"^(?:rs\.?|₹|\$)?\s*([+-]?\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?)",
        cleaned,
        flags=re.I,
    )
    if not match:
        return None
    try:
        return _evaluate_clean(match.group(1))
    except ArithmeticError:
        return None


def verify_line(line: str) -> bool | None:
    """True/False for an equality; None when it is not a machine equation."""
    if line.count("=") != 1:
        return None
    left, right = (part.strip() for part in line.split("=", 1))
    right = _strip_result_unit(right)
    try:
        return abs(evaluate(left) - evaluate(right)) <= Decimal("0.000001")
    except ArithmeticError:
        return None
