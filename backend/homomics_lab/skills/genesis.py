"""SkillGenesis — crystallize repeatedly-validated CodeAct scripts into skills.

This is the last mile of the self-improvement loop: the SkillDAG already
evolves observed edges and CBKB already records execution feedback, but the
*generated script itself* used to vanish after a successful CodeAct run, so
the next similar task had to be generated from scratch. SkillGenesis detects
proven scripts and proposes them as reusable community-trust skills:

Candidate signals (either is sufficient):
  a. The run succeeded *after* in-engine self-correction (``fix_history``
     non-empty) — the script has demonstrated robustness.
  b. The same normalized task signature (domain + action + input types, in
     the spirit of ``agent/plan/mode_selection_lore.IntentFeatures``) has
     succeeded at least ``settings.skill_genesis_min_successes`` times.

Candidate bookkeeping reuses the CBKB ``parameter_lore`` table (Layer 2,
"key parameter -> outcome quality") under the namespaced lore id
``genesis:<signature-hash>`` — no new table is introduced.

Every proposal is gated by HITL: a request is created in the shared
``PersistentApprovalStore`` (surfaced by the existing pending-approvals API)
and only an explicit approval imports the staged package into the SkillStore
as a COMMUNITY-trust skill. Rejection is recorded and the same signature is
never proposed again. Crystallized skills keep ``trust_level: community`` in
their SKILL.md frontmatter, so the existing trust model (no local sandbox,
no code cache for untrusted tiers) applies unchanged, and the standard
``SkillStore.trust_skill`` promotion path still works afterwards.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import yaml

from homomics_lab.config import settings
from homomics_lab.knowledge.cbkb import CBKB, ParameterLoreEntry

logger = logging.getLogger(__name__)

# Namespaced parameter-lore ids for genesis bookkeeping.
LORE_PREFIX = "genesis:"
METRIC_SUCCESS = "codeact_success"
METRIC_PROPOSED = "genesis_proposed"
METRIC_CRYSTALLIZED = "genesis_crystallized"
METRIC_REJECTED = "genesis_rejected"
STATUS_METRICS = (METRIC_PROPOSED, METRIC_CRYSTALLIZED, METRIC_REJECTED)

GENESIS_AUTHOR = "homomics-genesis"

# A notification describes one proposal; mirrors the pending-approval entry.
GenesisNotification = Dict[str, Any]
NotifyFn = Callable[[GenesisNotification], Any]


def _slugify(text: str, max_len: int = 40) -> str:
    """Normalize free text into a lowercase identifier fragment."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return slug[:max_len].strip("_") or "task"


@dataclass(frozen=True)
class TaskSignature:
    """Normalized, hashable identity of a CodeAct task.

    Intentionally lossy (like ``IntentFeatures``): domain + normalized action
    + sorted input file types, so repeated runs of the same kind of task
    collapse onto one key.
    """

    domain: str
    action: str
    input_types: Tuple[str, ...] = ()

    def key(self) -> str:
        return json.dumps(
            {
                "domain": self.domain,
                "action": self.action,
                "input_types": list(self.input_types),
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def hash(self) -> str:
        return hashlib.sha256(self.key().encode("utf-8")).hexdigest()[:16]

    @classmethod
    def build(
        cls,
        domain: Optional[str],
        action: Optional[str],
        input_types: Sequence[str] = (),
    ) -> "TaskSignature":
        return cls(
            domain=_slugify(domain or "general"),
            action=_slugify(action or "codeact_task"),
            input_types=tuple(sorted({t.lower() for t in input_types if t})),
        )


@dataclass
class GenesisCandidate:
    """A validated CodeAct script eligible for crystallization."""

    signature: TaskSignature
    code: str
    task_name: str
    project_id: str
    success_count: int
    had_fixes: bool
    fix_history: List[Dict[str, Any]] = field(default_factory=list)
    origin_skill: Optional[str] = None
    paths: Dict[str, str] = field(default_factory=dict)


@dataclass
class GenesisProposal:
    """A staged skill package awaiting human approval."""

    candidate: GenesisCandidate
    skill_id: str
    package_dir: Path
    call_id: str


class SkillGenesis:
    """Detect proven CodeAct scripts and crystallize them into community skills.

    All external effects are best-effort: genesis must never break a turn.

    Args:
        cbkb: Knowledge base used for candidate bookkeeping (parameter lore).
        skill_store: Store used to import approved packages. May be None in
            tests that only exercise detection/drafting.
        approval_store: HITL gate. Defaults to the shared persistent store.
        skill_dag: Optional DAG; crystallized skills are linked from their
            origin skill via the standard CANDIDATE proposal mechanism.
        llm_client: Optional LLM for drafting SKILL.md. When absent or
            unconfigured a deterministic template is used instead.
        notify: Optional callback invoked with a notification dict when a
            proposal is created (e.g. to push a chat/WebSocket message).
        min_successes: Signature success threshold (defaults to
            ``settings.skill_genesis_min_successes``).
        enabled: Defaults to ``settings.skill_genesis_enabled``.
        staging_dir: Where candidate packages are staged pending approval.
    """

    def __init__(
        self,
        cbkb: CBKB,
        skill_store: Optional[Any] = None,
        approval_store: Optional[Any] = None,
        skill_dag: Optional[Any] = None,
        llm_client: Optional[Any] = None,
        notify: Optional[NotifyFn] = None,
        min_successes: Optional[int] = None,
        enabled: Optional[bool] = None,
        staging_dir: Optional[Path] = None,
    ):
        self.cbkb = cbkb
        self.skill_store = skill_store
        if approval_store is None:
            from homomics_lab.tools.approval import get_default_approval_store

            approval_store = get_default_approval_store()
        self.approval_store = approval_store
        self.skill_dag = skill_dag
        self.llm_client = llm_client
        self.notify = notify
        self.min_successes = (
            min_successes
            if min_successes is not None
            else settings.skill_genesis_min_successes
        )
        self.enabled = (
            enabled if enabled is not None else settings.skill_genesis_enabled
        )
        self.staging_dir = Path(staging_dir or settings.data_dir / "skill_genesis")

    @classmethod
    def from_settings(cls, skill_dag: Optional[Any] = None) -> "SkillGenesis":
        """Build the default runtime instance from global settings/services."""
        from homomics_lab.skills.registry import get_default_registry
        from homomics_lab.skills.skill_store import SkillStore

        return cls(
            cbkb=CBKB(base_dir=settings.data_dir),
            skill_store=SkillStore(
                registry=get_default_registry(),
                store_dir=settings.data_dir / "skill_store",
                skills_dir=settings.skills_dir,
            ),
            skill_dag=skill_dag,
        )

    # ─────────────────────────────────────────
    # Candidate detection
    # ─────────────────────────────────────────

    async def record_execution(
        self,
        *,
        domain: Optional[str],
        action: Optional[str],
        input_types: Sequence[str] = (),
        task_name: str = "",
        code: str = "",
        success: bool = True,
        fix_history: Optional[List[Dict[str, Any]]] = None,
        project_id: str = "default",
        origin_skill: Optional[str] = None,
        paths: Optional[Dict[str, str]] = None,
    ) -> Optional[GenesisProposal]:
        """Record one CodeAct execution outcome; propose when it is proven.

        Returns a :class:`GenesisProposal` when this execution crossed a
        candidacy threshold and a HITL request was created, else None.
        """
        if not self.enabled:
            return None

        # Pick up decisions on earlier proposals (best-effort).
        try:
            await self.finalize_resolved()
        except Exception:
            logger.warning("SkillGenesis finalize pass failed", exc_info=True)

        if not success or not code or not code.strip():
            return None

        signature = TaskSignature.build(domain, action, input_types)
        fix_history = fix_history or []
        lore_id = self._lore_id(signature)

        self._add_lore(
            lore_id,
            param_name="task_signature",
            param_value=signature.key(),
            outcome_metric=METRIC_SUCCESS,
            outcome_value=1.0,
            project_id=project_id,
            context={
                "task_name": task_name,
                "code": code,
                "fix_history": fix_history,
                "origin_skill": origin_skill,
                "paths": paths or {},
            },
        )

        entries = self._lore_entries(lore_id)
        if any(e.outcome_metric in STATUS_METRICS for e in entries):
            # Already proposed / crystallized / rejected: never re-propose.
            return None

        success_count = sum(1 for e in entries if e.outcome_metric == METRIC_SUCCESS)
        had_fixes = bool(fix_history)
        if not had_fixes and success_count < self.min_successes:
            return None

        candidate = GenesisCandidate(
            signature=signature,
            code=code,
            task_name=task_name or signature.action,
            project_id=project_id,
            success_count=success_count,
            had_fixes=had_fixes,
            fix_history=fix_history,
            origin_skill=origin_skill,
            paths=paths or {},
        )
        try:
            return await self.propose(candidate)
        except Exception:
            logger.warning(
                "SkillGenesis proposal failed for signature %s",
                signature.key(),
                exc_info=True,
            )
            return None

    # ─────────────────────────────────────────
    # Crystallization
    # ─────────────────────────────────────────

    async def crystallize(self, candidate: GenesisCandidate) -> Path:
        """Draft SKILL.md + parameterized scripts and stage the package.

        The LLM (when configured) drafts the documentation from the proven
        script and its task context; a deterministic template is the
        fallback. Returns the staged package directory.
        """
        skill_id = self._skill_id_for(candidate)
        package_dir = self.staging_dir / skill_id
        scripts_dir = package_dir / "scripts" / "python"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        draft = await self._draft_with_llm(candidate) or self._fallback_draft(candidate)

        script = self._parameterize_code(candidate.code, candidate.paths)
        (scripts_dir / "core_analysis.py").write_text(script, encoding="utf-8")

        skill_md = self._build_skill_md(candidate, draft)
        (package_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
        return package_dir

    async def propose(self, candidate: GenesisCandidate) -> GenesisProposal:
        """Crystallize a candidate and open a HITL approval request."""
        package_dir = await self.crystallize(candidate)
        skill_id = self._skill_id_for(candidate)
        call_id = self._call_id(candidate.signature)

        self.approval_store.create_request(
            tool_name=f"skill_genesis:{skill_id}",
            arguments={
                "skill_id": skill_id,
                "task_signature": candidate.signature.key(),
                "task_name": candidate.task_name,
                "success_count": candidate.success_count,
                "had_fixes": candidate.had_fixes,
                "package_dir": str(package_dir),
            },
            risk_level="community",
            metadata={
                "kind": "skill_genesis",
                "skill_id": skill_id,
                "signature_hash": candidate.signature.hash(),
                "package_dir": str(package_dir),
                "project_id": candidate.project_id,
            },
            call_id=call_id,
        )

        self._add_lore(
            self._lore_id(candidate.signature),
            param_name="proposal",
            param_value=skill_id,
            outcome_metric=METRIC_PROPOSED,
            outcome_value=1.0,
            project_id=candidate.project_id,
            context={
                "call_id": call_id,
                "skill_id": skill_id,
                "package_dir": str(package_dir),
            },
        )

        await self._emit_notification(
            {
                "kind": "skill_genesis_proposal",
                "skill_id": skill_id,
                "call_id": call_id,
                "task_name": candidate.task_name,
                "project_id": candidate.project_id,
                "message": (
                    f"系统从成功执行中沉淀了新 skill '{skill_id}'，待确认 "
                    f"(approval call_id: {call_id})。"
                ),
            }
        )
        return GenesisProposal(
            candidate=candidate,
            skill_id=skill_id,
            package_dir=package_dir,
            call_id=call_id,
        )

    async def finalize_resolved(self) -> List[Any]:
        """Apply human decisions on pending proposals.

        Approved proposals are imported into the SkillStore as
        community-trust skills, recorded as CBKB knowledge
        ("task signature -> skill"), and linked into the SkillDAG through the
        standard runtime-proposal mechanism. Rejected proposals are recorded
        so the same signature is never proposed again. Returns the list of
        newly registered skills.
        """
        proposed: Dict[str, ParameterLoreEntry] = {}
        settled: set = set()
        for entry in self.cbkb.query_parameter_lore_by_prefix(LORE_PREFIX):
            lore_id = entry.skill_id
            if entry.outcome_metric in (METRIC_CRYSTALLIZED, METRIC_REJECTED):
                settled.add(lore_id)
            elif entry.outcome_metric == METRIC_PROPOSED and lore_id not in proposed:
                proposed[lore_id] = entry

        registered: List[Any] = []
        for lore_id, entry in proposed.items():
            if lore_id in settled:
                continue
            try:
                ctx = json.loads(entry.context or "{}")
            except json.JSONDecodeError:
                ctx = {}
            call_id = (
                ctx.get("call_id") or f"skill-genesis:{lore_id[len(LORE_PREFIX):]}"
            )
            resolution = self.approval_store.get_resolution(call_id)
            if resolution is None:
                continue  # still pending
            if resolution:
                skill = self._register_crystallized(lore_id, entry, ctx)
                if skill is not None:
                    registered.append(skill)
            else:
                self._add_lore(
                    lore_id,
                    param_name="rejection",
                    param_value=entry.param_value,
                    outcome_metric=METRIC_REJECTED,
                    outcome_value=0.0,
                    project_id=entry.project_id,
                    context={"call_id": call_id},
                )
                logger.info(
                    "Skill genesis proposal '%s' rejected; signature will not be re-proposed",
                    entry.param_value,
                )
        return registered

    # ─────────────────────────────────────────
    # Drafting helpers
    # ─────────────────────────────────────────

    async def _draft_with_llm(
        self, candidate: GenesisCandidate
    ) -> Optional[Dict[str, Any]]:
        """Ask the LLM for documentation fields; None when unavailable/invalid."""
        client = self.llm_client
        if client is None:
            try:
                from homomics_lab.llm_client import LLMClient

                client = LLMClient()
            except Exception:
                return None
        try:
            if not client.is_configured():
                return None
        except Exception:
            return None

        fixes = "\n".join(
            f"- attempt {f.get('attempt')}: {str(f.get('stderr', ''))[:200]}"
            for f in candidate.fix_history[:3]
        )
        prompt = (
            "A Python analysis script was generated by an agent and has been "
            "validated by successful execution. Draft reusable skill documentation "
            "for it as STRICT JSON with keys: name (short snake_case skill name), "
            "description (one sentence), keywords (list of 3-6 strings), inputs "
            "(object of param name -> {type, description}), outputs (object of "
            "name -> {type, description}), usage (markdown paragraph), parameters "
            "(markdown bullet list), notes (markdown bullet list of pitfalls).\n\n"
            f"Task: {candidate.task_name}\n"
            f"Domain: {candidate.signature.domain}\n"
            f"Validated successes: {candidate.success_count}\n"
            f"Self-correction fixes applied:\n{fixes or '- none'}\n\n"
            f"Script:\n```python\n{candidate.code[:6000]}\n```"
        )
        try:
            content = await client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You draft documentation for reusable bioinformatics skills. Reply with JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
            )
        except Exception:
            logger.warning(
                "SkillGenesis LLM drafting failed; using template", exc_info=True
            )
            return None
        return self._parse_draft(content)

    @staticmethod
    def _parse_draft(content: Any) -> Optional[Dict[str, Any]]:
        """Parse the LLM JSON draft, tolerating markdown fences."""
        if not isinstance(content, str) or not content.strip():
            return None
        text = content.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict) or not data.get("description"):
            return None
        return data

    @staticmethod
    def _fallback_draft(candidate: GenesisCandidate) -> Dict[str, Any]:
        """Deterministic documentation when no LLM is available."""
        return {
            "name": candidate.signature.action,
            "description": (
                f"Skill crystallized from a repeatedly validated CodeAct script "
                f"for '{candidate.task_name}' (domain: {candidate.signature.domain})."
            ),
            "keywords": ["genesis", "codeact", candidate.signature.domain],
            "inputs": {
                "input_path": {
                    "type": "string",
                    "description": "Path to the input data file",
                },
                "output_dir": {
                    "type": "string",
                    "description": "Directory for output files",
                },
            },
            "outputs": {
                "result": {"type": "object", "description": "Execution result summary"},
            },
            "usage": (
                "Read the reference script in `scripts/python/core_analysis.py` and "
                "adapt it to the concrete task. Placeholders of the form `<NAME>` "
                "mark parameters that were concrete paths in the original run."
            ),
            "parameters": (
                "- `input_path`: input data file\n"
                "- `output_dir`: directory that receives all outputs"
            ),
            "notes": (
                "- Crystallized from a script that succeeded "
                f"{candidate.success_count} time(s)"
                + (" after self-correction fixes" if candidate.had_fixes else "")
                + "\n- Community trust: review the script before relying on it"
            ),
        }

    @staticmethod
    def _parameterize_code(code: str, paths: Dict[str, str]) -> str:
        """Replace task-specific concrete paths with ``<NAME>`` placeholders.

        Skills are reference material (the agent reads and adapts them), so
        parameterization is textual and conservative. Absolute paths are
        rewritten as plain substrings (so ``<dir>/file.h5ad`` becomes
        ``<OUTPUT_DIR>/file.h5ad``), longest first so nested paths win over
        their prefixes; other values are only rewritten when quoted in full.
        """
        parameterized = code
        replacements: List[Tuple[str, str]] = []
        for name, value in sorted(
            (paths or {}).items(), key=lambda kv: -len(str(kv[1]))
        ):
            value = str(value)
            if not value or value in (".", "/"):
                continue
            token = f"<{re.sub(r'[^A-Z0-9]+', '_', name.upper()).strip('_')}>"
            replacements.append((value, token))
        header = [
            "# Crystallized by SkillGenesis from a validated CodeAct run.",
            "# Parameters (placeholders replaced from the original run):",
        ]
        for value, token in replacements:
            if Path(value).is_absolute():
                parameterized = parameterized.replace(value, token)
            else:
                for quote in ('"', "'"):
                    parameterized = parameterized.replace(
                        f"{quote}{value}{quote}", f'"{token}"'
                    )
        for name in paths or {}:
            token = f"<{re.sub(r'[^A-Z0-9]+', '_', name.upper()).strip('_')}>"
            header.append(f"#   {token}: original `{name}` parameter")
        header.append("")
        return "\n".join(header) + parameterized

    def _build_skill_md(
        self, candidate: GenesisCandidate, draft: Dict[str, Any]
    ) -> str:
        """Assemble SKILL.md with deterministic frontmatter + drafted body."""
        frontmatter = {
            "name": self._skill_id_for(candidate),
            "description": str(draft.get("description", "")).strip(),
            "category": "generated",
            "version": "1.0.0",
            "author": GENESIS_AUTHOR,
            "tool_type": "python",
            "trust_level": "community",
            "keywords": draft.get("keywords") or ["genesis", "codeact"],
            "inputs": draft.get("inputs") or {},
            "outputs": draft.get("outputs") or {},
        }
        body = f"""# {draft.get('name') or candidate.signature.action}

{draft.get('description', '')}

## Origin

- Crystallized by SkillGenesis from a validated CodeAct execution.
- Task: {candidate.task_name}
- Task signature: `{candidate.signature.key()}`
- Validated successes: {candidate.success_count}
- Self-correction fixes applied: {len(candidate.fix_history)}

## Usage

{draft.get('usage', '')}

## Parameters

{draft.get('parameters', '')}

## Notes

{draft.get('notes', '')}
"""
        return (
            "---\n"
            + yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
            + "---\n\n"
            + body
        )

    # ─────────────────────────────────────────
    # Registration / coordination
    # ─────────────────────────────────────────

    def _register_crystallized(
        self,
        lore_id: str,
        proposal_entry: ParameterLoreEntry,
        context: Dict[str, Any],
    ) -> Optional[Any]:
        """Import an approved package and record the resulting knowledge."""
        skill_id = proposal_entry.param_value
        package_dir = Path(context.get("package_dir") or self.staging_dir / skill_id)
        if not package_dir.exists():
            logger.warning(
                "Approved genesis package %s no longer exists; skipping", package_dir
            )
            return None

        skill = None
        if self.skill_store is not None:
            try:
                skill = self.skill_store.import_skill(
                    source=str(package_dir),
                    namespace="community",
                )
                # The SKILL.md frontmatter declares trust_level: community;
                # make sure the runtime metadata keeps it regardless of the
                # import-time source/trusted normalization.
                skill.metadata["trust_level"] = "community"
                self.skill_store.registry.register(skill)
            except Exception:
                logger.warning(
                    "Failed to import approved genesis skill '%s'",
                    skill_id,
                    exc_info=True,
                )
                return None

        # CBKB knowledge: "task signature -> crystallized skill".
        self._add_lore(
            lore_id,
            param_name="crystallized_skill",
            param_value=skill_id,
            outcome_metric=METRIC_CRYSTALLIZED,
            outcome_value=1.0,
            project_id=proposal_entry.project_id,
            context={"call_id": context.get("call_id"), "skill_id": skill_id},
        )

        # SkillDAG coordination: link from the origin (failed/absent) skill via
        # the standard CANDIDATE runtime proposal; promotion to CONFIRMED still
        # goes through the existing observed-edge thresholds.
        origin = self._origin_for(lore_id)
        if origin and self.skill_dag is not None:
            try:
                from homomics_lab.skills.skill_dag import EdgeType

                self.skill_dag.propose_edge(
                    origin,
                    skill_id,
                    EdgeType.ALTERNATIVE_TO,
                    context="SkillGenesis crystallized from CodeAct fallback success",
                    proposed_by="skill_genesis",
                )
            except Exception:
                logger.warning(
                    "Failed to link genesis skill into SkillDAG", exc_info=True
                )

        logger.info("Crystallized new community skill '%s' from genesis", skill_id)
        return skill

    def _origin_for(self, lore_id: str) -> Optional[str]:
        """Recover the origin skill recorded on the latest success entry."""
        for entry in self._lore_entries(lore_id):
            if entry.outcome_metric != METRIC_SUCCESS:
                continue
            try:
                ctx = json.loads(entry.context or "{}")
            except json.JSONDecodeError:
                continue
            if ctx.get("origin_skill"):
                return str(ctx["origin_skill"])
        return None

    # ─────────────────────────────────────────
    # Lore plumbing
    # ─────────────────────────────────────────

    @staticmethod
    def _lore_id(signature: TaskSignature) -> str:
        return f"{LORE_PREFIX}{signature.hash()}"

    @staticmethod
    def _call_id(signature: TaskSignature) -> str:
        return f"skill-genesis:{signature.hash()}"

    @staticmethod
    def _skill_id_for(candidate: GenesisCandidate) -> str:
        return f"genesis_{candidate.signature.action}_{candidate.signature.hash()[:6]}"

    def _lore_entries(self, lore_id: str) -> List[ParameterLoreEntry]:
        return self.cbkb.query_parameter_lore(skill_id=lore_id, limit=500)

    def _add_lore(
        self,
        lore_id: str,
        *,
        param_name: str,
        param_value: str,
        outcome_metric: str,
        outcome_value: float,
        project_id: str,
        context: Dict[str, Any],
    ) -> None:
        try:
            self.cbkb.add_parameter_lore(
                ParameterLoreEntry(
                    id=hashlib.sha256(
                        f"{lore_id}:{outcome_metric}:{uuid.uuid4().hex}".encode()
                    ).hexdigest()[:16],
                    skill_id=lore_id,
                    param_name=param_name,
                    param_value=param_value,
                    outcome_metric=outcome_metric,
                    outcome_value=outcome_value,
                    project_id=project_id,
                    context=json.dumps(context, ensure_ascii=False, default=str),
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        except Exception:
            logger.warning(
                "Failed to record genesis lore (%s)", outcome_metric, exc_info=True
            )

    async def _emit_notification(self, notification: GenesisNotification) -> None:
        """Deliver a proposal notification through the injected channel.

        The proposal is always visible via the shared approval store (the
        existing pending-approvals API); ``notify`` is an optional extra
        channel (chat message, WebSocket push, ...). Defaults to logging.
        """
        if self.notify is None:
            logger.info("Skill genesis proposal: %s", notification.get("message"))
            return
        try:
            result = self.notify(notification)
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.warning("SkillGenesis notification failed", exc_info=True)
