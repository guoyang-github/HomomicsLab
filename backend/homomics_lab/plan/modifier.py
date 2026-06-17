"""Structural plan modification.

PlanModifier applies user edits (add/remove phase, update dependencies,
update parameters) to a Plan while keeping the underlying PlanResult and
TaskTree consistent and the phase DAG valid.
"""

from typing import Dict, List, Set

from homomics_lab.agent.plan.models import Phase
from homomics_lab.plan.models import Plan, PlanModification
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.tasks.models import TaskNode


class PlanModifierError(Exception):
    """Raised when a plan modification is invalid or would break the DAG."""

    pass


class PlanModifier:
    """Apply structural and parametric modifications to a Plan."""

    @classmethod
    def apply(
        cls,
        plan: Plan,
        modifications: List[PlanModification],
    ) -> Plan:
        """Return a new Plan with modifications applied.

        The original plan is not mutated. The method validates that the
        resulting phase graph is still a DAG and that all phase references
        are consistent between PlanResult and TaskTree.
        """
        new_plan = plan.model_copy(deep=True)

        for mod in modifications:
            if mod.action == "update":
                cls._apply_param_update(new_plan, mod)
            elif mod.action == "remove":
                cls._apply_phase_remove(new_plan, mod)
            elif mod.action == "add":
                cls._apply_phase_add(new_plan, mod)
            elif mod.action == "update_dependency":
                cls._apply_dependency_update(new_plan, mod)
            else:
                raise PlanModifierError(f"Unknown modification action: {mod.action}")

        cls._validate(new_plan)
        return new_plan

    @staticmethod
    def _phase_lookup(plan: Plan) -> Dict[str, Phase]:
        return {p.phase_type: p for p in plan.plan_result.phases}

    @staticmethod
    def _task_lookup(plan: Plan) -> Dict[str, TaskNode]:
        return {t.name: t for t in plan.task_tree.tasks}

    @classmethod
    def _apply_param_update(cls, plan: Plan, mod: PlanModification) -> None:
        if mod.parameter is None:
            return
        phase = cls._phase_lookup(plan).get(mod.phase_type)
        task = cls._task_lookup(plan).get(mod.phase_type)
        if phase is not None:
            phase.parameters[mod.parameter] = mod.new_value
        if task is not None:
            task.parameters[mod.parameter] = mod.new_value

    @classmethod
    def _apply_phase_remove(cls, plan: Plan, mod: PlanModification) -> None:
        phase_type = mod.phase_type
        plan.plan_result.phases = [
            p for p in plan.plan_result.phases if p.phase_type != phase_type
        ]
        plan.task_tree.tasks = [
            t for t in plan.task_tree.tasks if t.name != phase_type
        ]
        plan.plan_result.phase_transitions = [
            t
            for t in plan.plan_result.phase_transitions
            if t.get("from") != phase_type and t.get("to") != phase_type
        ]

    @classmethod
    def _apply_phase_add(cls, plan: Plan, mod: PlanModification) -> None:
        phase_type = mod.phase_type
        if phase_type in cls._phase_lookup(plan):
            raise PlanModifierError(f"Phase '{phase_type}' already exists in plan")

        description = mod.description or f"{phase_type} analysis step"
        required = mod.required if mod.required is not None else True

        selected_skill = None
        if mod.skill_id:
            selected_skill = SkillDefinition(
                id=mod.skill_id,
                name=mod.skill_id,
                version="builtin",
                category=phase_type,
            )

        new_phase = Phase(
            phase_type=phase_type,
            required=required,
            description=description,
            selected_skill=selected_skill,
        )
        new_task = TaskNode(
            id=phase_type,
            name=phase_type,
            description=description,
            phase=phase_type,
            skills_required=[mod.skill_id] if mod.skill_id else [],
            dependencies=[],
        )

        phases = list(plan.plan_result.phases)
        tasks = list(plan.task_tree.tasks)

        if mod.after and mod.after in cls._phase_lookup(plan):
            after_index = next(
                i for i, p in enumerate(phases) if p.phase_type == mod.after
            )
            phases.insert(after_index + 1, new_phase)
            tasks.insert(after_index + 1, new_task)
            plan.plan_result.phase_transitions.append(
                {"from": mod.after, "to": phase_type, "type": "followed_by"}
            )
        elif mod.before and mod.before in cls._phase_lookup(plan):
            before_index = next(
                i for i, p in enumerate(phases) if p.phase_type == mod.before
            )
            phases.insert(before_index, new_phase)
            tasks.insert(before_index, new_task)
            plan.plan_result.phase_transitions.append(
                {"from": phase_type, "to": mod.before, "type": "followed_by"}
            )
        else:
            phases.append(new_phase)
            tasks.append(new_task)

        plan.plan_result.phases = phases
        plan.task_tree.tasks = tasks

        # If explicit dependencies are supplied, add them as transitions.
        if mod.dependencies:
            for dep in mod.dependencies:
                if dep in cls._phase_lookup(plan):
                    plan.plan_result.phase_transitions.append(
                        {"from": dep, "to": phase_type, "type": "followed_by"}
                    )

    @classmethod
    def _apply_dependency_update(cls, plan: Plan, mod: PlanModification) -> None:
        phase_type = mod.phase_type
        if phase_type not in cls._phase_lookup(plan):
            raise PlanModifierError(f"Phase '{phase_type}' not found")

        # Remove existing execution transitions to/from this phase.
        plan.plan_result.phase_transitions = [
            t
            for t in plan.plan_result.phase_transitions
            if not (
                t.get("type") in ("followed_by", "depends_on")
                and (t.get("from") == phase_type or t.get("to") == phase_type)
            )
        ]

        if mod.dependencies:
            for dep in mod.dependencies:
                if dep not in cls._phase_lookup(plan):
                    raise PlanModifierError(f"Dependency phase '{dep}' not found")
                plan.plan_result.phase_transitions.append(
                    {"from": dep, "to": phase_type, "type": "followed_by"}
                )

        # Sync task dependencies in the task tree.
        task = cls._task_lookup(plan).get(phase_type)
        if task is not None:
            task.dependencies = [
                cls._task_lookup(plan)[dep].id
                for dep in (mod.dependencies or [])
                if dep in cls._task_lookup(plan)
            ]

    @staticmethod
    def _validate(plan: Plan) -> None:
        """Validate that the modified plan is still a valid DAG."""
        phase_ids = {p.phase_type for p in plan.plan_result.phases}

        # All transitions must reference existing phases.
        for t in plan.plan_result.phase_transitions:
            from_phase = t.get("from")
            to_phase = t.get("to")
            if from_phase and from_phase not in phase_ids:
                raise PlanModifierError(f"Transition references unknown phase '{from_phase}'")
            if to_phase and to_phase not in phase_ids:
                raise PlanModifierError(f"Transition references unknown phase '{to_phase}'")

        # Detect cycles in execution transitions.
        graph: Dict[str, Set[str]] = {p: set() for p in phase_ids}
        for t in plan.plan_result.phase_transitions:
            if t.get("type") in ("followed_by", "depends_on"):
                from_phase = t.get("from")
                to_phase = t.get("to")
                if from_phase and to_phase:
                    graph[from_phase].add(to_phase)

        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                if has_cycle(node):
                    raise PlanModifierError("Modification would create a cyclic phase dependency")

        # Task tree phase names must match plan phases.
        task_names = {t.name for t in plan.task_tree.tasks}
        if task_names != phase_ids:
            raise PlanModifierError(
                f"Task tree phases {task_names} do not match plan phases {phase_ids}"
            )
