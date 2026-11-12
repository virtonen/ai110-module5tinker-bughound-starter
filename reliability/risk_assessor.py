import ast
import re
from typing import Dict, List


def _count_raises(code: str) -> int:
    """Count lines that start with `raise` (regex, not a full parse)."""
    return len(re.findall(r"^\s*raise\b", code, flags=re.MULTILINE))


def _string_literals(code: str):
    """Set of string constants in `code`, or None if it does not parse."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    return {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def assess_risk(
    original_code: str,
    fixed_code: str,
    issues: List[Dict[str, str]],
) -> Dict[str, object]:
    """
    Simple, explicit risk assessment used as a guardrail layer.

    Returns a dict with:
    - score: int from 0 to 100
    - level: "low" | "medium" | "high"
    - reasons: list of strings explaining deductions
    - should_autofix: bool
    """

    reasons: List[str] = []
    score = 100

    if not fixed_code.strip():
        return {
            "score": 0,
            "level": "high",
            "reasons": ["No fix was produced."],
            "should_autofix": False,
        }

    original_lines = original_code.strip().splitlines()
    fixed_lines = fixed_code.strip().splitlines()

    # ----------------------------
    # Issue severity based risk
    # ----------------------------
    for issue in issues:
        severity = str(issue.get("severity", "")).lower()

        if severity == "high":
            score -= 40
            reasons.append("High severity issue detected.")
        elif severity == "medium":
            score -= 20
            reasons.append("Medium severity issue detected.")
        elif severity == "low":
            score -= 5
            reasons.append("Low severity issue detected.")

    # ----------------------------
    # Structural change checks
    # ----------------------------
    if len(fixed_lines) < len(original_lines) * 0.5:
        score -= 20
        reasons.append("Fixed code is much shorter than original.")

    if "return" in original_code and "return" not in fixed_code:
        score -= 30
        reasons.append("Return statements may have been removed.")

    # Data safety: a string literal that vanished or changed means the fix edited runtime
    # data (e.g. a blind find/replace inside a string). The issue list can't tell us that.
    before, after = _string_literals(original_code), _string_literals(fixed_code)
    if before is not None and after is not None and not before <= after:
        score -= 30
        reasons.append("String literal(s) changed or removed; fix may alter runtime data.")

    # A new `raise` means callers that used to get a value (or a swallowed error)
    # may now get an exception. The issue list says nothing about this, so check the diff.
    if _count_raises(fixed_code) > _count_raises(original_code):
        score -= 20
        reasons.append("Fix introduces new raise statement(s); behavior on errors may have changed.")

    if "except:" in original_code and "except:" not in fixed_code:
        # This is usually good, but still risky.
        score -= 5
        reasons.append("Bare except was modified, verify correctness.")

    # ----------------------------
    # Clamp score
    # ----------------------------
    score = max(0, min(100, score))

    # ----------------------------
    # Risk level
    # ----------------------------
    if score >= 75:
        level = "low"
    elif score >= 40:
        level = "medium"
    else:
        level = "high"

    # ----------------------------
    # Auto-fix policy
    # ----------------------------
    should_autofix = level == "low"

    if not reasons:
        reasons.append("No significant risks detected.")

    return {
        "score": score,
        "level": level,
        "reasons": reasons,
        "should_autofix": should_autofix,
    }
