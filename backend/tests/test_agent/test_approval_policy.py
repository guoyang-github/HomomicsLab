from types import SimpleNamespace

from homomics_lab.agent.approval_policy import (
    DEFAULT_STRATEGY,
    normalize_strategy,
    plan_signature,
    resolve_strategy,
    should_require_approval,
)


def _task(skill_id=None, name="", skills_required=None):
    return SimpleNamespace(skill_id=skill_id, name=name, skills_required=skills_required)


def _tree(*tasks):
    return SimpleNamespace(tasks=list(tasks))


def test_normalize_strategy_falls_back_to_default():
    assert normalize_strategy("always") == "always"
    assert normalize_strategy("RISKY_ONLY") == "risky_only"
    assert normalize_strategy(None) == DEFAULT_STRATEGY
    assert normalize_strategy("bogus") == DEFAULT_STRATEGY
    assert normalize_strategy("") == DEFAULT_STRATEGY


def test_resolve_strategy_precedence_role_over_domain_over_global():
    role = SimpleNamespace(role_id="r1", plan_approval_strategy="never")
    domain = SimpleNamespace(
        roles=[role], plan_approval_strategy="first_time"
    )
    settings = SimpleNamespace(plan_approval_strategy="always")

    assert (
        resolve_strategy(domain_def=domain, role_id="r1", settings=settings)
        == "never"
    )
    assert (
        resolve_strategy(domain_def=domain, role_id=None, settings=settings)
        == "first_time"
    )
    assert (
        resolve_strategy(domain_def=None, role_id=None, settings=settings)
        == "always"
    )
    # No overrides anywhere -> default.
    assert resolve_strategy(domain_def=None, role_id=None, settings=None) == DEFAULT_STRATEGY


def test_plan_signature_is_order_independent():
    a = _tree(_task("bio-x"), _task("bio-y"))
    b = _tree(_task("bio-y"), _task("bio-x"))
    assert plan_signature(a) == plan_signature(b) == "bio-x|bio-y"
    assert plan_signature(None) == ""
    assert plan_signature(_tree()) == ""


def test_plan_signature_includes_strategy_name():
    tree = _tree(_task("bio-x"))
    assert plan_signature(tree, strategy_name="standalone") == "bio-x|strategy=standalone"


def test_plan_signature_prefers_skill_id_then_first_required_skill():
    tree = _tree(_task(skills_required=["bio-z"]))
    assert plan_signature(tree) == "bio-z"


def test_plan_mode_always_requires_approval():
    needs, _ = should_require_approval(
        strategy="never",
        plan=object(),
        tree=_tree(_task("bio-x")),
        is_high_risk=False,
        is_single_task_tree=True,
        plan_mode=True,
    )
    assert needs is True


def test_high_risk_always_requires_approval_even_when_never():
    needs, _ = should_require_approval(
        strategy="never",
        plan=object(),
        tree=_tree(_task("bio-x"), _task("bio-y")),
        is_high_risk=True,
        is_single_task_tree=False,
        plan_mode=False,
    )
    assert needs is True


def test_single_task_tree_runs_under_every_strategy():
    for strategy in ("always", "first_time", "risky_only", "never"):
        needs, _ = should_require_approval(
            strategy=strategy,
            plan=object(),
            tree=_tree(_task("bio-x")),
            is_high_risk=False,
            is_single_task_tree=True,
        )
        assert needs is False


def test_never_strategy_skips_gate_for_low_risk_plans():
    needs, _ = should_require_approval(
        strategy="never",
        plan=object(),
        tree=_tree(_task("bio-x"), _task("bio-y")),
        is_high_risk=False,
        is_single_task_tree=False,
    )
    assert needs is False


def test_always_strategy_gates_non_trivial_plans():
    needs, _ = should_require_approval(
        strategy="always",
        plan=object(),
        tree=_tree(_task("bio-x"), _task("bio-y")),
        is_high_risk=False,
        is_single_task_tree=False,
    )
    assert needs is True


def test_risky_only_runs_low_risk_plans_without_confirmation():
    needs, _ = should_require_approval(
        strategy="risky_only",
        plan=object(),
        tree=_tree(_task("bio-x"), _task("bio-y")),
        is_high_risk=False,
        is_single_task_tree=False,
    )
    assert needs is False


def test_first_time_confirms_once_then_remembers():
    seen = ["existing-signature"]
    tree = _tree(_task("bio-x"), _task("bio-y"))
    plan = SimpleNamespace(strategy_name="test-strategy")

    first, updated = should_require_approval(
        strategy="first_time",
        plan=plan,
        tree=tree,
        is_high_risk=False,
        is_single_task_tree=False,
        seen_signatures=seen,
    )
    # The signature should NOT be recorded yet (user may reject).
    assert first is True
    assert updated == seen

    # Simulate caller recording the signature after execution.
    sig = plan_signature(tree, strategy_name=plan.strategy_name)
    seen.append(sig)

    second, _ = should_require_approval(
        strategy="first_time",
        plan=plan,
        tree=tree,
        is_high_risk=False,
        is_single_task_tree=False,
        seen_signatures=seen,
    )
    assert second is False


def test_no_plan_never_gates():
    needs, _ = should_require_approval(
        strategy="always",
        plan=None,
        tree=_tree(_task("bio-x")),
        is_high_risk=False,
        is_single_task_tree=False,
    )
    assert needs is False
