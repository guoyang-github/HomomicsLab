from homics_lab.skills.runtime import SkillRuntimeExecutor
from .data_loader import DATA_LOADER_SKILL, DATA_LOADER_CODE
from .scanpy_qc import SCANPY_QC_SKILL, SCANPY_QC_CODE
from .scanpy_cluster import SCANPY_CLUSTER_SKILL, SCANPY_CLUSTER_CODE


def register_builtin_skills(executor: SkillRuntimeExecutor) -> None:
    executor.register_builtin(DATA_LOADER_SKILL, DATA_LOADER_CODE)
    executor.register_builtin(SCANPY_QC_SKILL, SCANPY_QC_CODE)
    executor.register_builtin(SCANPY_CLUSTER_SKILL, SCANPY_CLUSTER_CODE)
