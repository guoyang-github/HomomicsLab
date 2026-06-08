import uuid
from typing import Any, Dict, List
from homics_lab.agent.intent_analyzer import UserIntent
from homics_lab.models.common import AgentType, HITLCheckpoint, Option
from homics_lab.tasks.models import TaskNode
from homics_lab.tasks.task_tree import TaskTree


class TaskDecomposer:
    """Decomposes user intent into executable task trees."""

    SINGLE_CELL_PIPELINE = [
        {
            "name": "quality_control",
            "description": "Filter low-quality cells and genes",
            "phase": "preprocessing",
            "agent": AgentType.BIOINFO,
            "skills": ["scanpy_qc"],
        },
        {
            "name": "dimensionality_reduction",
            "description": "Compute PCA on normalized data",
            "phase": "analysis",
            "agent": AgentType.BIOINFO,
            "skills": ["scanpy_pca"],
            "dependencies": ["quality_control"],
        },
        {
            "name": "clustering",
            "description": "Compute neighbors and UMAP embedding",
            "phase": "analysis",
            "agent": AgentType.BIOINFO,
            "skills": ["scanpy_cluster"],
            "dependencies": ["dimensionality_reduction"],
            "hitl": ["n_neighbors", "resolution"],
        },
        {
            "name": "cell_annotation",
            "description": "Annotate cell clusters with marker genes",
            "phase": "analysis",
            "agent": AgentType.BIOINFO,
            "skills": ["scanpy_annotation"],
            "dependencies": ["clustering"],
        },
        {
            "name": "differential_expression",
            "description": "Find marker genes for each cluster",
            "phase": "analysis",
            "agent": AgentType.BIOINFO,
            "skills": ["scanpy_de"],
            "dependencies": ["cell_annotation"],
        },
        {
            "name": "visualization",
            "description": "Generate UMAP plots and heatmaps",
            "phase": "reporting",
            "agent": AgentType.VIZ,
            "skills": ["plot_umap", "plot_heatmap"],
            "dependencies": ["clustering", "cell_annotation"],
        },
    ]

    async def decompose(self, intent: UserIntent, context: Dict[str, Any]) -> TaskTree:
        if intent.analysis_type == "single_cell_analysis" and intent.complexity == "complex":
            return self._build_single_cell_pipeline(context)
        elif intent.analysis_type == "file_conversion":
            return self._build_single_step("convert_file", "Convert file format", ["data_loader"])
        elif intent.analysis_type == "qa":
            return self._build_single_step("answer_question", "Answer user question", [])
        else:
            return self._build_single_step(
                "general_analysis",
                f"General {intent.analysis_type} analysis",
                ["data_loader"],
            )

    def _build_single_cell_pipeline(self, context: Dict[str, Any]) -> TaskTree:
        tasks = []
        id_map = {}

        for step in self.SINGLE_CELL_PIPELINE:
            task_id = str(uuid.uuid4())[:8]
            id_map[step["name"]] = task_id

            dependencies = [
                id_map[dep] for dep in step.get("dependencies", [])
                if dep in id_map
            ]

            hitl_checkpoints = []
            if "hitl" in step:
                hitl_checkpoints.append(HITLCheckpoint(
                    id=f"hitl_{task_id}",
                    trigger_reason="policy",
                    context_summary=f"Please confirm parameters for {step['name']}: {', '.join(step['hitl'])}",
                    options=[
                        Option(id="default", label="Use defaults", description="Use recommended parameter values"),
                        Option(id="custom", label="Customize", description="Set custom parameter values"),
                    ],
                ))

            task = TaskNode(
                id=task_id,
                name=step["name"],
                description=step["description"],
                phase=step["phase"],
                agent_assignment=step["agent"],
                skills_required=step["skills"],
                dependencies=dependencies,
                hitl_checkpoints=hitl_checkpoints,
            )
            tasks.append(task)

        return TaskTree(tasks)

    def _build_single_step(self, name: str, description: str, skills: List[str]) -> TaskTree:
        task = TaskNode(
            id=str(uuid.uuid4())[:8],
            name=name,
            description=description,
            phase="execution",
            skills_required=skills,
        )
        return TaskTree([task])
