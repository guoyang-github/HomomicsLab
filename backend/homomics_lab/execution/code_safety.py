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
    AST_SENSITIVE_MODULES = {"os", "subprocess", "importlib"}
    AST_SENSITIVE_STRINGS = {"os", "subprocess", "importlib", "eval", "exec", "__import__"}

    # Calls that are harmless for normal file I/O inside the project workspace.
    AST_SAFE_OS_CALLS = {
        "os.makedirs",
        "os.path.join",
        "os.path.dirname",
        "os.path.basename",
        "os.path.abspath",
        "os.path.exists",
        "os.path.isdir",
        "os.path.isfile",
        "os.path.expanduser",
        "os.listdir",
        "os.walk",
        "os.getenv",
        "os.environ.get",
    }

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
                    elif func.id == "getattr" and len(node.args) >= 2:
                        # getattr(os, "sys"+"tem") style dynamic access.
                        base = node.args[0]
                        if isinstance(base, ast.Name) and base.id in self.AST_SENSITIVE_MODULES:
                            findings.append(f"[high] Dynamic attribute access on {base.id}: getattr({base.id}, ...)")
                elif isinstance(func, ast.Attribute):
                    full = self._attribute_full_name(func)
                    if full in self.AST_FORBIDDEN_MODULES:
                        findings.append(f"[critical] Forbidden call: {full}()")
                    elif full in self.AST_SAFE_OS_CALLS:
                        # Harmless workspace path/file helpers: keep the finding
                        # at low severity so it does not trigger HITL by default.
                        findings.append(f"[low] Safe workspace helper: {full}()")
                    else:
                        # Any other method call on a sensitive module is flagged.
                        root = self._attribute_root_name(func)
                        if root in self.AST_SENSITIVE_MODULES:
                            findings.append(f"[high] Sensitive module call: {full}()")
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                # Detect string concatenation used to build dangerous literals,
                # e.g. "__im"+"port__" or "ev"+"al".
                left = self._string_literal(node.left)
                right = self._string_literal(node.right)
                if left is not None and right is not None:
                    combined = left + right
                    if combined in self.AST_SENSITIVE_STRINGS:
                        findings.append(f"[high] String concatenation builds sensitive literal: {combined!r}")
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

    @staticmethod
    def _attribute_root_name(node: ast.Attribute) -> str:
        """Return the leftmost name of an attribute chain, e.g. 'os' for 'os.system'."""
        current: ast.expr = node.value
        while isinstance(current, ast.Attribute):
            current = current.value
        if isinstance(current, ast.Name):
            return current.id
        return ""

    @staticmethod
    def _string_literal(node: ast.expr) -> str | None:
        """Extract a plain string literal from an AST node."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None


def requires_hitl(result: SafetyScanResult, min_risk_level: str = "high") -> bool:
    """Return True if the scan result requires human-in-the-loop approval."""
    if min_risk_level == "never":
        return False
    levels = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    return levels.get(result.risk_level, 0) >= levels.get(min_risk_level, 2)
