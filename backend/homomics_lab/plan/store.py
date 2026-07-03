"""Async repository for persisted execution plans."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select

from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.database.connection import AsyncSessionLocal
from homomics_lab.database.models import PlanRecord, PlanTemplateRecord
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import (
    TaskTree,
    build_dependencies_from_phase_transitions,
)

from .models import Plan, PlanModification, PlanStatus
from .modifier import PlanModifier


def _new_plan_id() -> str:
    return f"plan_{uuid.uuid4().hex[:12]}"


def _serialize_task_tree(tree: Optional[TaskTree]) -> Optional[str]:
    if tree is None:
        return None
    return json.dumps([t.model_dump(mode="json") for t in tree.tasks])


def _deserialize_task_tree(raw: Optional[str]) -> Optional[TaskTree]:
    if raw is None:
        return None
    tasks = [TaskNode.model_validate(d) for d in json.loads(raw)]
    return TaskTree(tasks)


def _deserialize_working_memory(raw: Optional[str]) -> Optional[WorkingMemory]:
    if raw is None:
        return None
    return WorkingMemory.from_json(raw)


class PlanStore:
    """Persist and retrieve execution plans from SQLite."""

    def __init__(self, session_factory=AsyncSessionLocal):
        self._session_factory = session_factory

    async def create(self, plan: Plan) -> Plan:
        """Persist a new plan."""
        async with self._session_factory() as session:
            record = self._to_record(plan)
            session.add(record)
            await session.commit()
            return plan

    async def get(self, plan_id: str) -> Optional[Plan]:
        """Retrieve a plan by ID."""
        async with self._session_factory() as session:
            record = await session.get(PlanRecord, plan_id)
            return self._to_model(record) if record else None

    async def update(self, plan: Plan) -> Plan:
        """Update an existing plan."""
        async with self._session_factory() as session:
            record = await session.get(PlanRecord, plan.plan_id)
            if record is None:
                raise ValueError(f"Plan {plan.plan_id} not found")
            self._update_record(record, plan)
            await session.commit()
            return plan

    async def approve(
        self,
        plan_id: str,
        approved_by: str = "user",
    ) -> Plan:
        """Mark a plan as approved."""
        plan = await self.get(plan_id)
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")
        plan.status = PlanStatus.APPROVED
        plan.approved_by = approved_by
        plan.approved_at = datetime.now(timezone.utc)
        plan.updated_at = datetime.now(timezone.utc)
        return await self.update(plan)

    async def reject(self, plan_id: str) -> Plan:
        """Mark a plan as rejected."""
        plan = await self.get(plan_id)
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")
        plan.status = PlanStatus.REJECTED
        plan.updated_at = datetime.now(timezone.utc)
        return await self.update(plan)

    async def update_status(self, plan_id: str, status: str) -> Plan:
        """Update the lifecycle status of a plan."""
        plan = await self.get(plan_id)
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")
        plan.status = status
        plan.updated_at = datetime.now(timezone.utc)
        return await self.update(plan)

    async def modify(
        self,
        plan_id: str,
        modifications: List[PlanModification],
        approved: bool = False,
        approved_by: Optional[str] = None,
    ) -> Plan:
        """Create a new plan version with applied modifications."""
        original = await self.get(plan_id)
        if original is None:
            raise ValueError(f"Plan {plan_id} not found")

        # Normalize modifications to PlanModification objects.
        normalized: List[PlanModification] = []
        for mod in modifications:
            if isinstance(mod, PlanModification):
                normalized.append(mod)
            elif isinstance(mod, dict):
                normalized.append(PlanModification.model_validate(mod))
            else:
                raise ValueError(f"Invalid modification type: {type(mod)}")

        new_plan = PlanModifier.apply(original, normalized)
        new_plan.plan_id = _new_plan_id()
        new_plan.parent_plan_id = original.plan_id
        new_plan.version = original.version + 1
        new_plan.status = PlanStatus.APPROVED if approved else PlanStatus.PENDING_APPROVAL
        new_plan.approved_by = approved_by if approved else None
        new_plan.approved_at = datetime.now(timezone.utc) if approved else None
        new_plan.created_at = datetime.now(timezone.utc)
        new_plan.updated_at = datetime.now(timezone.utc)

        await self.create(new_plan)
        return new_plan

    @staticmethod
    def diff(plan_a: Plan, plan_b: Plan) -> List[Dict[str, Any]]:
        """Return a list of differences between two plan versions."""
        differences: List[Dict[str, Any]] = []
        a_phases = {p.phase_type: p for p in plan_a.plan_result.phases}
        b_phases = {p.phase_type: p for p in plan_b.plan_result.phases}

        for phase_type in set(a_phases) | set(b_phases):
            a_phase = a_phases.get(phase_type)
            b_phase = b_phases.get(phase_type)
            if a_phase is None:
                differences.append({"phase_type": phase_type, "change": "added"})
                continue
            if b_phase is None:
                differences.append({"phase_type": phase_type, "change": "removed"})
                continue

            # Compare skill
            a_skill = a_phase.selected_skill.id if a_phase.selected_skill else None
            b_skill = b_phase.selected_skill.id if b_phase.selected_skill else None
            if a_skill != b_skill:
                differences.append(
                    {
                        "phase_type": phase_type,
                        "change": "skill_changed",
                        "old": a_skill,
                        "new": b_skill,
                    }
                )

            # Compare parameters
            all_keys = set(a_phase.parameters.keys()) | set(b_phase.parameters.keys())
            for key in all_keys:
                a_val = a_phase.parameters.get(key)
                b_val = b_phase.parameters.get(key)
                if a_val != b_val:
                    differences.append(
                        {
                            "phase_type": phase_type,
                            "change": "parameter_changed",
                            "parameter": key,
                            "old": a_val,
                            "new": b_val,
                        }
                    )

        return differences

    async def list_by_session(
        self,
        session_id: str,
        parent_plan_id: Optional[str] = None,
    ) -> List[Plan]:
        """List plans for a session, optionally filtered by parent plan."""
        async with self._session_factory() as session:
            stmt = select(PlanRecord).where(PlanRecord.session_id == session_id)
            if parent_plan_id is not None:
                stmt = stmt.where(PlanRecord.parent_plan_id == parent_plan_id)
            stmt = stmt.order_by(desc(PlanRecord.created_at))
            result = await session.execute(stmt)
            return [self._to_model(r) for r in result.scalars().all()]

    async def list_all(
        self,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Plan]:
        """List plans, optionally filtered by project and status."""
        async with self._session_factory() as session:
            stmt = select(PlanRecord)
            if project_id:
                stmt = stmt.where(PlanRecord.project_id == project_id)
            if status:
                stmt = stmt.where(PlanRecord.status == status)
            stmt = stmt.order_by(desc(PlanRecord.created_at))
            result = await session.execute(stmt)
            return [self._to_model(r) for r in result.scalars().all()]

    async def list_versions(self, plan_id: str) -> List[Plan]:
        """Return the version chain for a plan (itself + children)."""
        plan = await self.get(plan_id)
        if plan is None:
            return []
        parent_id = plan.parent_plan_id or plan.plan_id
        async with self._session_factory() as session:
            stmt = (
                select(PlanRecord)
                .where(
                    (PlanRecord.plan_id == parent_id)
                    | (PlanRecord.parent_plan_id == parent_id)
                )
                .order_by(desc(PlanRecord.version), desc(PlanRecord.created_at))
            )
            result = await session.execute(stmt)
            return [self._to_model(r) for r in result.scalars().all()]

    @staticmethod
    def _to_record(plan: Plan) -> PlanRecord:
        return PlanRecord(
            plan_id=plan.plan_id,
            session_id=plan.session_id,
            project_id=plan.project_id,
            status=plan.status,
            is_fallback=plan.is_fallback,
            intent_analysis_type=plan.intent_analysis_type,
            intent_complexity=plan.intent_complexity,
            original_intent_json=(
                json.dumps(plan.original_intent, default=str)
                if plan.original_intent is not None
                else None
            ),
            plan_result_json=json.dumps(plan.plan_result.to_dict()),
            task_tree_json=_serialize_task_tree(plan.task_tree),
            working_memory_json=(
                plan.working_memory.to_json() if plan.working_memory else None
            ),
            approved_by=plan.approved_by,
            approved_at=plan.approved_at,
            parent_plan_id=plan.parent_plan_id,
            version=plan.version,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )

    @staticmethod
    def _update_record(record: PlanRecord, plan: Plan) -> None:
        record.status = plan.status
        record.is_fallback = plan.is_fallback
        record.intent_analysis_type = plan.intent_analysis_type
        record.intent_complexity = plan.intent_complexity
        record.original_intent_json = (
            json.dumps(plan.original_intent, default=str)
            if plan.original_intent is not None
            else None
        )
        record.plan_result_json = json.dumps(plan.plan_result.to_dict())
        record.task_tree_json = _serialize_task_tree(plan.task_tree)
        record.working_memory_json = (
            plan.working_memory.to_json() if plan.working_memory else None
        )
        record.approved_by = plan.approved_by
        record.approved_at = plan.approved_at
        record.parent_plan_id = plan.parent_plan_id
        record.version = plan.version
        record.updated_at = plan.updated_at

    @staticmethod
    def _to_model(record: PlanRecord) -> Plan:
        from homomics_lab.agent.plan.models import PlanResult

        return Plan(
            plan_id=record.plan_id,
            session_id=record.session_id,
            project_id=record.project_id,
            status=record.status,
            is_fallback=record.is_fallback,
            intent_analysis_type=record.intent_analysis_type,
            intent_complexity=record.intent_complexity,
            original_intent=json.loads(record.original_intent_json)
            if record.original_intent_json
            else None,
            plan_result=PlanResult.from_dict(json.loads(record.plan_result_json)),
            task_tree=_deserialize_task_tree(record.task_tree_json),
            working_memory=_deserialize_working_memory(record.working_memory_json),
            approved_by=record.approved_by,
            approved_at=record.approved_at,
            parent_plan_id=record.parent_plan_id,
            version=record.version,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def save_template(
        self,
        plan_id: str,
        name: str,
    ) -> str:
        """Save a plan as a reusable template."""
        plan = await self.get(plan_id)
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")
        template_id = f"template_{uuid.uuid4().hex[:12]}"
        record = PlanTemplateRecord(
            template_id=template_id,
            name=name,
            plan_result_json=json.dumps(plan.plan_result.to_dict()),
        )
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()
        return template_id

    async def list_templates(self) -> List[Dict[str, Any]]:
        """List all reusable plan templates."""
        async with self._session_factory() as session:
            stmt = select(PlanTemplateRecord).order_by(desc(PlanTemplateRecord.created_at))
            result = await session.execute(stmt)
            return [
                {
                    "template_id": r.template_id,
                    "name": r.name,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in result.scalars().all()
            ]

    async def load_template(
        self,
        template_id: str,
        session_id: str,
        project_id: str,
    ) -> Plan:
        """Create a new plan from a reusable template."""
        from homomics_lab.agent.plan.models import PlanResult

        async with self._session_factory() as session:
            record = await session.get(PlanTemplateRecord, template_id)
        if record is None:
            raise ValueError(f"Template {template_id} not found")
        plan_result = PlanResult.from_dict(json.loads(record.plan_result_json))
        task_ids = [phase.phase_type for phase in plan_result.phases]
        incoming = build_dependencies_from_phase_transitions(
            task_ids, plan_result.phase_transitions
        )
        task_tree = TaskTree(
            tasks=[
                TaskNode(
                    id=phase.phase_type,
                    name=phase.phase_type,
                    description=phase.description,
                    phase=phase.phase_type,
                    skills_required=[phase.selected_skill.id]
                    if phase.selected_skill is not None
                    else [],
                    parameters=phase.parameters,
                    dependencies=list(
                        dict.fromkeys(incoming.get(phase.phase_type, []))
                    ),
                )
                for phase in plan_result.phases
            ]
        )
        new_plan_id = _new_plan_id()
        new_plan = Plan(
            plan_id=new_plan_id,
            session_id=session_id,
            project_id=project_id,
            status=PlanStatus.PENDING_APPROVAL,
            is_fallback=False,
            intent_analysis_type="template",
            intent_complexity="complex",
            plan_result=plan_result,
            task_tree=task_tree,
            version=1,
        )
        async with self._session_factory() as session:
            session.add(self._to_record(new_plan))
            await session.commit()
        return new_plan
