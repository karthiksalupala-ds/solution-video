"""Deliberately small safe evaluator for display arithmetic equalities."""

from __future__ import annotations

import ast
import re
from decimal import Decimal, InvalidOperation


class ArithmeticError(ValueError):
    """The expression uses unsupported or invalid arithmetic."""


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


def evaluate(expression: str) -> Decimal:
    return _evaluate_clean(expression)


def verify_line(line: str) -> bool | None:
    """True/False for an equality; None when it is not a machine equation."""
    if line.count("=") != 1:
        return None
    left, right = (part.strip() for part in line.split("=", 1))
    # Remove display-only units only at the end of an expression.
    left = re.sub(r"\s*(km/h|m/s|days?|meters?|metres?|rs|lakh)\s*$", "", left, flags=re.I)
    right = re.sub(r"\s*(km/h|m/s|days?|meters?|metres?|rs|lakh)\s*$", "", right, flags=re.I)
    try:
        return abs(evaluate(left) - evaluate(right)) <= Decimal("0.000001")
    except ArithmeticError:
        return None
