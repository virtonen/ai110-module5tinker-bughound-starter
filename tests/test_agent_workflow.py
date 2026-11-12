from bughound_agent import BugHoundAgent
from llm_client import MockClient


def test_workflow_runs_in_offline_mode_and_returns_shape():
    agent = BugHoundAgent(client=None)  # heuristic-only
    code = "def f():\n    print('hi')\n    return True\n"
    result = agent.run(code)

    assert isinstance(result, dict)
    assert "issues" in result
    assert "fixed_code" in result
    assert "risk" in result
    assert "logs" in result

    assert isinstance(result["issues"], list)
    assert isinstance(result["fixed_code"], str)
    assert isinstance(result["risk"], dict)
    assert isinstance(result["logs"], list)
    assert len(result["logs"]) > 0


def test_offline_mode_detects_print_issue():
    agent = BugHoundAgent(client=None)
    code = "def f():\n    print('hi')\n    return True\n"
    result = agent.run(code)

    assert any(issue.get("type") == "Code Quality" for issue in result["issues"])


def test_offline_mode_proposes_logging_fix_for_print():
    agent = BugHoundAgent(client=None)
    code = "def f():\n    print('hi')\n    return True\n"
    result = agent.run(code)

    fixed = result["fixed_code"]
    assert "logging" in fixed
    assert "logging.info(" in fixed


def test_mock_client_forces_llm_fallback_to_heuristics_for_analysis():
    # MockClient returns non-JSON for analyzer prompts, so agent should fall back.
    agent = BugHoundAgent(client=MockClient())
    code = "def f():\n    print('hi')\n    return True\n"
    result = agent.run(code)

    assert any(issue.get("type") == "Code Quality" for issue in result["issues"])
    # Ensure we logged the fallback path
    assert any("Falling back to heuristics" in entry.get("message", "") for entry in result["logs"])


class FakeClient:
    """Returns a fixed analyzer response so we can test parsing without an API."""

    def __init__(self, response):
        self.response = response

    def complete(self, system_prompt, user_prompt):
        return self.response


CODE = "def f():\n    print('hi')\n    return True\n"


def _analyze(response):
    agent = BugHoundAgent(client=FakeClient(response))
    return agent.analyze(CODE), agent.logs


def test_valid_llm_json_is_accepted_and_severity_normalized():
    issues, _ = _analyze('[{"type": "Bug", "severity": "high", "msg": "bad thing"}]')
    assert issues == [{"type": "Bug", "severity": "High", "msg": "bad thing"}]


def test_empty_array_means_no_issues_not_fallback():
    issues, logs = _analyze("[]")
    assert issues == []
    assert not any("Falling back" in e["message"] for e in logs)


def test_items_missing_msg_trigger_fallback_instead_of_fake_issue():
    issues, logs = _analyze('[{"foo": 1}]')
    assert any(i["type"] == "Code Quality" for i in issues)  # heuristic result
    assert any("Falling back to heuristics" in e["message"] for e in logs)


def test_non_object_items_trigger_fallback_instead_of_silent_empty():
    issues, logs = _analyze('["a string", 3]')
    assert any(i["type"] == "Code Quality" for i in issues)
    assert any("not an object" in e["message"] for e in logs)


def test_invalid_severity_triggers_fallback():
    issues, logs = _analyze('[{"type": "X", "severity": "Critical", "msg": "m"}]')
    assert any("invalid severity" in e["message"] for e in logs)


def test_one_bad_item_rejects_whole_array():
    _, logs = _analyze('[{"severity": "Low", "msg": "ok"}, {"severity": "Low"}]')
    assert any("Falling back to heuristics" in e["message"] for e in logs)
