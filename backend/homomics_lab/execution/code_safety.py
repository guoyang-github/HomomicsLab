"""Code safety scanner for CodeAct generated code.

Provides static analysis to detect high-risk patterns and determine whether
human approval is required before execution.
"""

import ast
import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class SafetyScanResult:
    """Result of scanning generated code for safety issues."""

    safe: bool
    risk_level: str  # "low" | "medium" | "high" | "critical"
    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "safe": self.safe,
            "risk_level": self.risk_level,
            "findings": self.findings,
        }


class CodeSafetyScanner:
    """Static scanner for generated Python/R/Bash code."""

    # Patterns that indicate dangerous operations.
    DANGEROUS_PATTERNS = {
        "critical": [
            (r"\bos\.system\b", "Direct os.system call"),
            (r"\bsubprocess\.call\s*\(\s*[^)]*shell\s*=\s*True", "subprocess with shell=True"),
            (r"\bsubprocess\.Popen\s*\(\s*[^)]*shell\s*=\s*True", "subprocess.Popen with shell=True"),
            (r"\beval\s*\(", "eval() usage"),
            (r"\bexec\s*\(", "exec() usage"),
            (r"\bcompile\s*\(", "compile() usage"),
        ],
        "high": [
            (r"\brm\s+-rf\b", "Recursive force remove"),
            (r"\bformat\s*\(|%s", "Potential format string exploitation"),
            (r"\b__import__\s*\(", "Dynamic import via __import__"),
            (r"\bimportlib\.import_module\s*\(", "Dynamic import via importlib"),
            (r"\brequests\.get\b|\burllib\.request\.urlopen\b", "Network request"),
            (r"\bsocket\.", "Socket usage"),
            (r"\bsmtplib\.", "SMTP/email usage"),
            (r"\bshutil\.rmtree\b", "Recursive directory removal"),
        ],
        "medium": [
            (r"\bopen\s*\(\s*[^,)]*,\s*['\"]w", "File write operation"),
            (r"\bopen\s*\(\s*[^,)]*,\s*['\"]a", "File append operation"),
            (r"\bos\.remove\b", "File deletion"),
            (r"\bos\.unlink\b", "File deletion"),
            (r"\bsubprocess\.", "Subprocess usage"),
            (r"\bpathlib\.Path\b.*\.unlink\b", "Path.unlink deletion"),
        ],
    }

    # AST-level checks for Python code.
    AST_FORBIDDEN_NAMES = {"__import__", "eval", "exec", "compile"}
    AST_FORBIDDEN_MODULES = {"os.system", "subprocess.call", "subprocess.Popen"}

    def scan(self, code: str, language: str = "python") -> SafetyScanResult:
        """Scan code and return a safety report."""
        findings: List[str] = []

        if language == "python":
            findings.extend(self._ast_scan(code))

        text = code
        for level, patterns in self.DANGEROUS_PATTERNS.items():
            for pattern, description in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    findings.append(f"[{level}] {description}")

        if not findings:
            return SafetyScanResult(safe=True, risk_level="low", findings=[])

        # Determine overall risk level from highest finding.
        if any(f.startswith("[critical]") for f in findings):
            risk_level = "critical"
        elif any(f.startswith("[high]") for f in findings):
            risk_level = "high"
        elif any(f.startswith("[medium]") for f in findings):
            risk_level = "medium"
        else:
            risk_level = "low"

        return SafetyScanResult(
            safe=False,
            risk_level=risk_level,
            findings=findings,
        )

    def _ast_scan(self, code: str) -> List[str]:
        """Use Python AST to detect forbidden calls and imports."""
        findings: List[str] = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    if func.id in self.AST_FORBIDDEN_NAMES:
                        findings.append(f"[critical] Forbidden call: {func.id}()")
                elif isinstance(func, ast.Attribute):
                    full = self._attribute_full_name(func)
                    if full in self.AST_FORBIDDEN_MODULES:
                        findings.append(f"[critical] Forbidden call: {full}()")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in {"os", "subprocess", "socket", "smtplib"}:
                        findings.append(f"[medium] Imports module: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module in {"os", "subprocess", "socket", "smtplib"}:
                    findings.append(f"[medium] Imports from {node.module}")

        return findings

    @staticmethod
    def _attribute_full_name(node: ast.Attribute) -> str:
        """Build 'module.submodule.func' from an attribute access AST node."""
        parts = [node.attr]
        current: ast.expr = node.value
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))


def requires_hitl(result: SafetyScanResult, min_risk_level: str = "high") -> bool:
    """Return True if the scan result requires human-in-the-loop approval."""
    if min_risk_level == "never":
        return False
    levels = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    return levels.get(result.risk_level, 0) >= levels.get(min_risk_level, 2)
