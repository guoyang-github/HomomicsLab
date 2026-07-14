"""Visualization edit handler — apply natural-language edits to the most recent plot.

This module implements the fast path described in the product brief:
when the user sends a message like "换成箱线图" / "加误差线" / "换个配色",
the agent locates the most recent plot in working memory and re-renders it
by mutating the Plotly figure directly.  The new figure is returned as a
``PLOT_DATA`` chat message so the frontend can update the existing figure card.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional

from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.viz.edit_engine import PlotlyEditEngine

if TYPE_CHECKING:
    from homomics_lab.agent.intent_analyzer import UserIntent
    from homomics_lab.agent.turn_runner import TurnRunner
    from homomics_lab.context.working_memory import WorkingMemory


class VisualizationEditHandler:
    """Handle ``visualization_edit`` intents by editing the latest plot."""

    # Message types that may carry a renderable figure.
    _PLOT_MESSAGE_TYPES = (MessageType.PLOT_DATA, MessageType.PLOT)

    def __init__(self, runner: "TurnRunner"):
        self._runner = runner

    async def handle(
        self,
        user_message: str,
        working_memory: "WorkingMemory",
        project_id: str,
        intent: Optional["UserIntent"] = None,
    ) -> TurnResult:
        """Apply a natural-language edit to the most recent plot.

        Args:
            user_message: The raw user request (e.g. "把颜色改成蓝色").
            working_memory: Current session working memory.
            project_id: Active project identifier.
            intent: The classified ``visualization_edit`` intent (optional).

        Returns:
            ``TurnResult`` containing the edited plot as a ``PLOT_DATA`` message,
            or a text fallback when no recent plot exists or the edit cannot be
            applied deterministically.
        """
        latest_plot = self._find_latest_plot_message(working_memory)
        if latest_plot is None:
            return self._fallback_result(
                "我找不到最近的图，无法进行修改。请先生成一张图后再试试。",
                working_memory,
            )

        original_content = latest_plot.content
        if not isinstance(original_content, dict):
            return self._fallback_result(
                "当前图的消息格式不支持直接编辑。",
                working_memory,
            )

        # ``PLOT_DATA`` content is ``{plot_type, title, caption, data, layout}``,
        # which is already a valid Plotly figure with extra top-level metadata.
        figure = original_content

        if not figure.get("data"):
            return self._fallback_result(
                "我只支持编辑交互式 Plotly 图表，当前图无法直接修改。",
                working_memory,
            )

        edited_figure = PlotlyEditEngine.apply(user_message, figure)
        if edited_figure is None:
            return self._fallback_result(
                "我理解了您的改图意图，但暂时无法自动应用这个修改。",
                working_memory,
            )

        new_content: Dict[str, Any] = {
            **original_content,
            "data": edited_figure["data"],
            "layout": edited_figure["layout"],
        }
        # Preserve the plot_type if it was stored at the top level.
        if "plot_type" in original_content:
            new_content["plot_type"] = original_content["plot_type"]
        if "title" in original_content:
            new_content["title"] = edited_figure["layout"].get("title", original_content["title"])

        plot_msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.PLOT_DATA,
            content=new_content,
            sender="agent",
            task_id=latest_plot.task_id,
            skill_id=latest_plot.skill_id,
        )
        working_memory.add_message(plot_msg)

        return TurnResult(
            mode=ExecutionMode.DIRECT_RESPONSE,
            response_text="已按您的要求更新图表。",
            agent_message=plot_msg,
            attachments=[plot_msg],
        )

    def _find_latest_plot_message(
        self, working_memory: "WorkingMemory"
    ) -> Optional[ChatMessage]:
        """Return the most recent plot or plot_data message, if any."""
        for msg in reversed(list(working_memory.messages)):
            try:
                if MessageType(msg.type) in self._PLOT_MESSAGE_TYPES:
                    return msg
            except Exception:
                continue
        return None

    def _fallback_result(
        self, response_text: str, working_memory: "WorkingMemory"
    ) -> TurnResult:
        """Return a text-only result when the edit cannot be applied."""
        msg = ChatMessage(
            id=f"msg_{len(working_memory.messages)}",
            type=MessageType.TEXT,
            content=response_text,
            sender="agent",
        )
        working_memory.add_message(msg)
        return TurnResult(
            mode=ExecutionMode.DIRECT_RESPONSE,
            response_text=response_text,
            agent_message=msg,
        )
