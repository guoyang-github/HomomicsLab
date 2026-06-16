"""Tests for CodeAct safety scanner."""


from homomics_lab.execution.code_safety import CodeSafetyScanner, requires_hitl


def test_safe_code_passes():
    scanner = CodeSafetyScanner()
    result = scanner.scan("result = 1 + 1\nprint(result)")
    assert result.safe is True
    assert result.risk_level == "low"


def test_detects_eval():
    scanner = CodeSafetyScanner()
    result = scanner.scan("eval('1+1')")
    assert result.safe is False
    assert result.risk_level == "critical"
    assert any("eval" in f for f in result.findings)


def test_detects_shell_true():
    scanner = CodeSafetyScanner()
    result = scanner.scan("import subprocess\nsubprocess.call('ls', shell=True)")
    assert result.safe is False
    assert result.risk_level == "critical"


def test_detects_network_request():
    scanner = CodeSafetyScanner()
    result = scanner.scan("import requests\nr = requests.get('http://example.com')")
    assert result.safe is False
    assert result.risk_level == "high"


def test_hitl_required_for_high():
    scanner = CodeSafetyScanner()
    result = scanner.scan("import requests\nr = requests.get('http://example.com')")
    assert requires_hitl(result, min_risk_level="high") is True
    assert requires_hitl(result, min_risk_level="critical") is False


def test_hitl_never():
    scanner = CodeSafetyScanner()
    result = scanner.scan("eval('1+1')")
    assert requires_hitl(result, min_risk_level="never") is False
