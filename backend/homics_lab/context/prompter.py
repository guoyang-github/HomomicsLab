from typing import Any
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

        # Find "User:" section to preserve
        user_idx = prompt.rfind("User:")
        if user_idx == -1:
            user_idx = len(prompt)

        system_part = prompt[:user_idx]
        user_part = prompt[user_idx:]

        system_words = system_part.split()
        user_words = user_part.split()

        # Reserve space for user message
        reserved_for_user = min(len(user_words), max_words // 4)
        available_for_system = max_words - reserved_for_user

        if available_for_system <= 0:
            # Not enough space, return just user part truncated
            return "...\n\n" + " ".join(user_words[:max_words])

        truncated_system = " ".join(system_words[:available_for_system])
        truncated_user = " ".join(user_words[:reserved_for_user])

        return truncated_system + "\n\n... [context truncated] ...\n\n" + truncated_user
