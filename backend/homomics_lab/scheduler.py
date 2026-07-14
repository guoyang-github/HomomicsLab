"""APScheduler-based scheduled task integration for HomomicsLab."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import desc, select

from homomics_lab.config import settings
from homomics_lab.database.connection import AsyncSessionLocal
from homomics_lab.database.models import ScheduledJobRun
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.knowledge.curator import CBKBCurator
from homomics_lab.skills.registry import get_default_registry
from homomics_lab.skills.skill_dag import SkillDAG

logger = logging.getLogger(__name__)

JobCoroutine = Callable[..., Coroutine[Any, Any, Any]]


class HomomicsScheduler:
    """Wraps APScheduler and provides scheduled curation and evolution jobs."""

    def __init__(self):
        self._scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
        self._curator: Optional[CBKBCurator] = None
        self._evolution_engine: Optional[Any] = None

    @property
    def scheduler(self) -> AsyncIOScheduler:
        """The underlying APScheduler instance (for one-shot timer jobs)."""
        return self._scheduler

    def set_context(self, ctx: Dict[str, Any]) -> None:
        """Receive bootstrap context so the scheduler can use the live SkillDAG."""
        skill_dag = ctx.get("skill_dag")
        if skill_dag is None:
            return
        cbkb = CBKB(settings.data_dir)
        self._curator = CBKBCurator(cbkb, skill_dag=skill_dag)
        self._build_evolution_engine(cbkb, skill_dag)

    def _build_evolution_engine(self, cbkb: CBKB, skill_dag: SkillDAG) -> None:
        """Build the EvolutionEngine from live registries."""
        from homomics_lab.agent.factory import create_default_agents
        from homomics_lab.agent.plan.engine import PlanEngine
        from homomics_lab.evolution.engine import EvolutionEngine

        core = create_default_agents()
        plan_engine = PlanEngine(
            skill_registry=skill_dag.registry,
            skill_dag=skill_dag,
            cbkb=cbkb,
        )
        self._evolution_engine = EvolutionEngine(
            cbkb=cbkb,
            skill_dag=skill_dag,
            plan_engine=plan_engine,
            role_registry=core.role_registry,
        )

    async def start(self) -> None:
        """Register configured jobs and start the scheduler."""
        if self._curator is None:
            self._curator = CBKBCurator(CBKB(settings.data_dir))
        if self._evolution_engine is None:
            self._build_evolution_engine(CBKB(settings.data_dir), SkillDAG(registry=get_default_registry(), db_path=settings.data_dir / "skill_dag.db"))

        if settings.curation_enabled:
            self._add_cron_job(
                "cbkb_full_curation",
                settings.curation_schedule,
                self._run_full_curation,
            )
        if settings.narrative_report_enabled:
            self._add_cron_job(
                "narrative_report",
                settings.narrative_report_schedule,
                self._run_narrative_report,
            )
        if settings.sop_proposal_enabled:
            self._add_cron_job(
                "sop_proposal",
                settings.sop_proposal_schedule,
                self._run_sop_proposal,
            )
        if settings.evolution_enabled:
            self._add_cron_job(
                "evolution_pass",
                settings.evolution_schedule,
                self._run_evolution_pass,
            )

        if settings.scheduler_run_at_startup:
            # Schedule all enabled jobs to run a few seconds after startup.
            for name, enabled, fn in [
                ("cbkb_full_curation", settings.curation_enabled, self._run_full_curation),
                ("narrative_report", settings.narrative_report_enabled, self._run_narrative_report),
                ("sop_proposal", settings.sop_proposal_enabled, self._run_sop_proposal),
                ("evolution_pass", settings.evolution_enabled, self._run_evolution_pass),
            ]:
                if enabled:
                    self._scheduler.add_job(
                        fn,
                        trigger=DateTrigger(),
                        id=f"{name}_startup",
                        name=f"{name}_startup",
                        replace_existing=True,
                        max_instances=1,
                    )

        self._scheduler.start()
        logger.info("Scheduler started with %d jobs", len(self._scheduler.get_jobs()))

    async def shutdown(self) -> None:
        """Stop the scheduler gracefully."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=True)
            logger.info("Scheduler stopped")

    async def run_now(self, job_name: str) -> Optional[ScheduledJobRun]:
        """Manually trigger a scheduled job by name.

        Returns the audit record for the run, or None if the job is unknown/disabled.
        """
        mapping: Dict[str, JobCoroutine] = {
            "cbkb_full_curation": self._run_full_curation,
            "narrative_report": self._run_narrative_report,
            "sop_proposal": self._run_sop_proposal,
            "evolution_pass": self._run_evolution_pass,
        }
        fn = mapping.get(job_name)
        if fn is None:
            raise ValueError(f"Unknown scheduled job: {job_name}")
        if self._curator is None:
            self._curator = CBKBCurator(CBKB(settings.data_dir))
        return await self._run_task(job_name, fn)

    def _add_cron_job(
        self,
        name: str,
        schedule: str,
        coro_fn: JobCoroutine,
    ) -> None:
        trigger = CronTrigger.from_crontab(schedule, timezone=settings.scheduler_timezone)
        self._scheduler.add_job(
            coro_fn,
            trigger=trigger,
            id=name,
            name=name,
            replace_existing=True,
            max_instances=1,
        )
        logger.info("Registered scheduled job %s with schedule %s", name, schedule)

    async def _run_full_curation(self) -> None:
        await self._run_task("cbkb_full_curation", self._curator.run_full_curation)

    async def _run_narrative_report(self) -> None:
        await self._run_task(
            "narrative_report",
            self._curator.generate_narrative,
            1,
        )

    async def _run_sop_proposal(self) -> None:
        await self._run_task("sop_proposal", self._curator.propose_sop_updates)

    async def _run_evolution_pass(self) -> None:
        if self._evolution_engine is None:
            logger.warning("EvolutionEngine not initialized; skipping evolution_pass")
            return
        await self._run_task("evolution_pass", self._evolution_engine.run_evolution_pass)

    async def _run_task(
        self,
        job_name: str,
        coro_fn: JobCoroutine,
        *args: Any,
    ) -> ScheduledJobRun:
        """Execute a scheduled coroutine and persist an audit record."""
        trigger_time = datetime.now(timezone.utc)
        run = await self._record_start(job_name, trigger_time)
        try:
            result = await coro_fn(*args)
            result_json = json.dumps(self._serialize_result(result))
            await self._record_end(run, status="completed", result_json=result_json)
            logger.info("Scheduled job %s completed", job_name)
        except Exception as exc:
            logger.exception("Scheduled job %s failed", job_name)
            await self._record_end(run, status="failed", error_message=str(exc))
        return run

    @staticmethod
    def _serialize_result(result: Any) -> Any:
        """Convert dataclasses / lists to JSON-friendly dicts."""
        from dataclasses import asdict, is_dataclass

        if is_dataclass(result):
            return asdict(result)
        if isinstance(result, list) and result and is_dataclass(result[0]):
            return [asdict(item) for item in result]
        if isinstance(result, dict):
            return result
        return {"summary": str(result)}

    async def _record_start(
        self,
        job_name: str,
        trigger_time: datetime,
    ) -> ScheduledJobRun:
        run = ScheduledJobRun(
            job_name=job_name,
            trigger_time=trigger_time,
            start_time=datetime.now(timezone.utc),
            status="running",
        )
        async with AsyncSessionLocal() as session:
            session.add(run)
            await session.commit()
            await session.refresh(run)
        return run

    async def _record_end(
        self,
        run: ScheduledJobRun,
        status: str,
        result_json: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        run.status = status
        run.end_time = datetime.now(timezone.utc)
        run.result_json = result_json
        run.error_message = error_message
        async with AsyncSessionLocal() as session:
            await session.merge(run)
            await session.commit()

    async def recent_runs(
        self,
        job_name: Optional[str] = None,
        limit: int = 20,
    ) -> list[ScheduledJobRun]:
        async with AsyncSessionLocal() as session:
            stmt = select(ScheduledJobRun)
            if job_name:
                stmt = stmt.where(ScheduledJobRun.job_name == job_name)
            stmt = stmt.order_by(desc(ScheduledJobRun.start_time)).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())
