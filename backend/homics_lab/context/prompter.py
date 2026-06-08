from typing import Any, Dict, Optional
from homics_lab.context.working_memory import WorkingMemory


class Prompter:
    """Assembles LLM prompts from layered memory."""

    def __init__(self, token_budget: int = 4000):
        self.token_budget = token_budget
        self.words_per_token = 0.75  # Rough estimate

    def build_prompt(
        self,
        user_message: str,
        working_memory: WorkingMemory,
        task: Any = None,
        project_context: str = "",
        user_profile: str = "",
    ) -> str:
        parts = []

        # System prompt
        parts.append(self._system_prompt())

        # User profile
        if user_profile:
            parts.append(f"User Profile:\n{user_profile}")

        # Project context
        if project_context:
            parts.append(f"Project Context:\n{project_context}")

        # Recent messages
        recent_msgs = working_memory.get_recent_messages(10)
        if recent_msgs:
            history = "\n".join(
                f"{msg.sender}: {msg.content}"
                for msg in recent_msgs
            )
            parts.append(f"Recent Conversation:\n{history}")

        # Current task
        if task:
            parts.append(f"Current Task: {task.name} - {task.description}")
            if task.parameters:
                params = "\n".join(f"  {k}: {v}" for k, v in task.parameters.items())
                parts.append(f"Task Parameters:\n{params}")

        # User current message
        parts.append(f"User: {user_message}")
        parts.append("Assistant:")

        prompt = "\n\n".join(parts)
        return self._truncate_if_needed(prompt)

    def _system_prompt(self) -> str:
        return """You are HomicsLab, an AI assistant specialized in bioinformatics analysis.
You help researchers design experiments, analyze omics data, and interpret results.
Be concise, accurate, and ask for clarification when needed."""

    def _truncate_if_needed(self, prompt: str) -> str:
        words = prompt.split()
        max_words = int(self.token_budget * self.words_per_token)

        if len(words) <= max_words:
            return prompt

        # Simple truncation from the middle (keep system + user message)
        # A more sophisticated approach would use the relevance filter
        system_end = words.index("Assistant:") if "Assistant:" in words else 0
        user_idx = prompt.rfind("User:")
        user_part = prompt[user_idx:] if user_idx > 0 else ""

        head_words = words[:max_words - len(user_part.split()) - 10]
        return " ".join(head_words) + "\n\n... [context truncated] ...\n\n" + user_part
