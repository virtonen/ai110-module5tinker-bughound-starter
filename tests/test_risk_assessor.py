from reliability.risk_assessor import assess_risk


def test_no_fix_is_high_risk():
    risk = assess_risk(
        original_code="print('hi')\n",
        fixed_code="",
        issues=[{"type": "Code Quality", "severity": "Low", "msg": "print"}],
    )
    assert risk["level"] == "high"
    assert risk["should_autofix"] is False
    assert risk["score"] == 0


def test_low_risk_when_minimal_change_and_low_severity():
    original = "import logging\n\ndef add(a, b):\n    return a + b\n"
    fixed = "import logging\n\ndef add(a, b):\n    return a + b\n"
    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[{"type": "Code Quality", "severity": "Low", "msg": "minor"}],
    )
    assert risk["level"] in ("low", "medium")  # depends on scoring rules
    assert 0 <= risk["score"] <= 100


def test_high_severity_issue_drives_score_down():
    original = "def f():\n    try:\n        return 1\n    except:\n        return 0\n"
    fixed = "def f():\n    try:\n        return 1\n    except Exception as e:\n        return 0\n"
    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[{"type": "Reliability", "severity": "High", "msg": "bare except"}],
    )
    assert risk["score"] <= 60
    assert risk["level"] in ("medium", "high")


def test_missing_return_is_penalized():
    original = "def f(x):\n    return x + 1\n"
    fixed = "def f(x):\n    x + 1\n"
    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[],
    )
    assert risk["score"] < 100
    assert any("Return" in r or "return" in r for r in risk["reasons"])


def test_new_raise_is_penalized_even_with_only_low_severity_issues():
    original = "def f(x, y):\n    try:\n        return x / y\n    except:\n        return 0\n"
    fixed = (
        "def f(x, y):\n    if y is None:\n        raise TypeError('y')\n"
        "    try:\n        return x / y\n    except ZeroDivisionError:\n        return 0\n"
    )
    risk = assess_risk(original, fixed, [{"type": "Code Quality", "severity": "Low", "msg": "m"}])
    assert any("raise" in r for r in risk["reasons"])
    assert risk["should_autofix"] is False


def test_existing_raise_is_not_penalized():
    code = "def f(x):\n    if x < 0:\n        raise ValueError('neg')\n    return x\n"
    risk = assess_risk(code, code, [])
    assert not any("raise" in r for r in risk["reasons"])
    assert risk["should_autofix"] is True
