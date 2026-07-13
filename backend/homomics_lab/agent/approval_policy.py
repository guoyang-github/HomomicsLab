"""Plan-approval policy.

Resolves *when* a generated plan must pause for human confirmation before
execution. The policy is configurable so that trusted, low-risk analyses can
run end-to-end without a click, while uncertain or high-risk plans still gate.

Strategies (resolved role -> domain -> global, defaulting to ``risky_only``):

* ``always``     — every non-trivial plan requires confirmation.
* ``first_time`` — confirm each distinct plan shape once per session, then
                   auto-execute identical plans.
* ``risky_only`` — only high-risk or fallback plans require confirmation;
                   curated low-risk plans run immediately (default).
* ``never``      — never pause on the plan gate (high-risk/fallback still
                   gate via the safety invariant below).

Two invariants override every strategy:

1. Explicit ``plan_mode`` always surfaces the plan (the user asked to review it).
2. Fallback or ``risk_level == "high"`` plans always require confirmation.
   This module only governs the *plan-level* gate; high-risk *tool* calls and
   unsafe code are still enforced by ``tools/approval`` and the code-safety
   HITL path and are never bypassed here.
"""

from typing import Any, Optional, Set

APPROVAL_STRATEGIES = ("always", "first_time", "risky_only", "never")
DEFAULT_STRATEGY = "risky_only"


def normalize_strategy(value: Optional[str]) -> str:
    """Return a valid strategy, falling back to the default for unknown values."""
    strategy = (value or "").strip().lower()
    return strategy if strategy in APPROVAL_STRATEGIES else DEFAULT_STRATEGY


def resolve_strategy(
    *,
    domain_def: Any = None,
    role_id: Optional[str] = None,
    settings: Any = None,
) -> str:
    """Resolve the effective strategy: role override > domain override > global."""
    if domain_def is not None and role_id:
        role = next(
            (r for r in getattr(domain_def, "roles", []) if r.role_id == role_id),
            None,
        )
        role_strategy = getattr(role, "plan_approval_strategy", None) if role else None
        if role_strategy:
            return normalize_strategy(role_strategy)

    domain_strategy = getattr(domain_def, "plan_approval_strategy", None) if domain_def else None
    if domain_strategy:
        return normalize_strategy(domain_strategy)

    global_strategy = getattr(settings, "plan_approval_strategy", None) if settings else None
    return normalize_strategy(global_strategy)


def plan_signature(tree: Any) -> str:
    """Stable identity for a plan shape, used by the ``first_time`` strategy."""
    if tree is None or not getattr(tree, "tasks", None):
        return ""
    parts = sorted(
        (getattr(task, "skill_id", None) or getattr(task, "name", "") or "")
        for task in tree.tasks
    )
    return "|".join(parts)


def should_require_approval(
    *,
    strategy: str,
    plan: Any,
    tree: Any,
    is_high_risk: bool,
    is_single_task_tree: bool,
    plan_mode: bool = False,
    seen_signatures: Optional[Set[str]] = None,
) -> bool:
    """Decide whether the plan gate should pause for human confirmation."""
    strategy = normalize_strategy(strategy)

    # Invariant 1: explicit plan mode always reviews the plan.
    if plan_mode:
        return True
    # Invariant 2: uncertainty/risk always gates, regardless of strategy.
    if is_high_risk:
        return True
    if plan is None:
        return False
    # A single, dependency-free, low-risk named task is an unambiguous
    # instruction (e.g. "use CellTypist on sample.h5ad"); run it directly.
    if is_single_task_tree:
        return False

    if strategy == "never":
        return False
    if strategy == "always":
        return True
    if strategy == "first_time":
        signature = plan_signature(tree)
        if seen_signatures is None:
            return True
        if signature and signature in seen_signatures:
            return False
        if signature:
            seen_signatures.add(signature)
        return True

    # risky_only (default): curated low-risk plans auto-execute.
    return False
