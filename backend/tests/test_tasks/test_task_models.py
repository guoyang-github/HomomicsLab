from homomics_lab.tasks.models import TaskNode, TaskStatus, RetryPolicy
from homomics_lab.models.common import HITLTrigger


def test_task_node_defaults():
    task = TaskNode(id="t1", name="test", description="test task")
    assert task.status == TaskStatus.PENDING
    assert task.dependencies == []
    assert task.skills_required == []


def test_retry_policy_defaults():
    policy = RetryPolicy()
    assert policy.max_attempts == 3
    assert policy.backoff_seconds == 2.0


def test_task_with_hitl():
    task = TaskNode(
        id="t2",
        name="clustering",
        description="cluster cells",
        hitl_checkpoints=[{
            "trigger_reason": HITLTrigger.POLICY,
            "context_summary": "Please confirm clustering parameters",
            "options": [{"id": "default", "label": "Use defaults"}],
        }],
    )
    assert len(task.hitl_checkpoints) == 1
    assert task.hitl_checkpoints[0].trigger_reason == HITLTrigger.POLICY
