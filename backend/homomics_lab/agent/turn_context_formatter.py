"""ContextFormatter — formats MCP/science tool outputs and conversation context.

Extracted from ``turn_runner.TurnRunner`` as a pure code move (no logic
changes).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from homomics_lab.agent.turn_runner import TurnRunner
    from homomics_lab.context.working_memory import WorkingMemory


class ContextFormatter:
    """Format tool outputs, extra context and working-memory history for prompts."""

    def __init__(self, runner: "TurnRunner"):
        self._runner = runner

    def working_memory_to_history(
        self, working_memory: "WorkingMemory"
    ) -> List[Dict[str, Any]]:
        """Convert recent working-memory messages to OpenAI-compatible history."""
        history: List[Dict[str, Any]] = []
        for msg in working_memory.get_recent_messages()[-10:]:
            if msg.sender == "user":
                role = "user"
            elif msg.sender == "agent":
                role = "assistant"
            else:
                continue
            content = msg.content
            if isinstance(content, dict):
                content = (
                    content.get("response_text") or content.get("text") or str(content)
                )
            if not isinstance(content, str):
                content = str(content)
            history.append({"role": role, "content": content})
        return history

    @staticmethod
    def summarize_mcp_result(
        tool_name: str,
        output: Any,
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a useful text summary from an MCP tool output."""
        if not isinstance(output, dict):
            return f"{tool_name} 调用完成"

        error = output.get("error")
        if error:
            return f"工具返回错误：{error}"

        if tool_name == "pubmed_search":
            return ContextFormatter.format_pubmed_search(output, tool_inputs)
        if tool_name == "pubmed_fetch":
            return ContextFormatter.format_pubmed_fetch(output, tool_inputs)
        if tool_name == "science_search":
            return ContextFormatter.format_science_search(output, tool_inputs)
        if tool_name == "science_list_dbs":
            return ContextFormatter.format_science_dbs(output)

        count = output.get("count")
        if count is not None:
            return f"{tool_name} 返回 {count} 条结果"
        return f"{tool_name} 调用完成"

    @staticmethod
    def format_pubmed_search(
        output: Dict[str, Any],
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format PubMed search results into a readable Markdown list."""
        from urllib.parse import quote

        query = ""
        if isinstance(tool_inputs, dict):
            query = tool_inputs.get("query", "") or ""
        count = output.get("count", "0")
        try:
            count_int = int(count)
        except (TypeError, ValueError):
            count_int = 0

        encoded_query = quote(query.encode("utf-8")) if query else ""
        pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/?term={encoded_query}"

        if count_int == 0:
            return (
                f"未找到与“{query}”相关的 PubMed 文献。\n\n"
                "建议：\n"
                "- 尝试用英文关键词或同义词；\n"
                "- 去掉过于具体的限定词，扩大检索范围；\n"
                "- 直接提供 PMID 或 DOI，我可以帮你解读。\n\n"
                f"[在 PubMed 中打开检索]({pubmed_url})"
            )

        articles = output.get("articles", []) or []
        lines = [f"找到 {count_int} 条相关文献，以下是前 {len(articles)} 条：\n"]
        for idx, article in enumerate(articles, start=1):
            if not isinstance(article, dict):
                continue
            title = article.get("title", "未知标题") or "未知标题"
            authors = article.get("authors", []) or []
            authors_str = ", ".join(authors[:3])
            if len(authors) > 3:
                authors_str += " et al."
            journal = article.get("journal", "") or ""
            pubdate = article.get("pubdate", "") or ""
            pmid = article.get("pmid", "") or ""
            doi = article.get("doi", "") or ""
            pmid_link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
            parts = [
                p
                for p in [authors_str, f"*{journal}*" if journal else "", pubdate]
                if p
            ]
            meta = " · ".join(parts)
            pmid_part = f" · PMID: [{pmid}]({pmid_link})" if pmid else ""
            doi_part = f" · DOI: {doi}" if doi else ""
            lines.append(f"{idx}. **{title}**  \n   {meta}{pmid_part}{doi_part}")

        lines.append(f"\n[在 PubMed 中查看全部结果]({pubmed_url})")
        return "\n".join(lines)

    @staticmethod
    def format_science_dbs(output: Dict[str, Any]) -> str:
        """Format the science database catalog into a readable list."""
        databases = output.get("databases", []) or []
        if not databases:
            return "当前没有可用的科学数据库连接器。"
        lines = ["可查询的科学数据库：\n"]
        for db in databases:
            if not isinstance(db, dict):
                continue
            name = db.get("name", "?")
            desc = db.get("description", "") or ""
            available = db.get("available", True)
            badge = "可用" if available else "不可用（缺少依赖或密钥）"
            suffix = f" — {desc}" if desc else ""
            lines.append(f"- **{name}** [{badge}]{suffix}")
        return "\n".join(lines)

    @staticmethod
    def format_science_search(
        output: Dict[str, Any],
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format merged science_search results into a readable Markdown list."""
        query = ""
        if isinstance(tool_inputs, dict):
            query = tool_inputs.get("query", "") or ""
        results = output.get("results", []) or []
        databases = output.get("databases", []) or []
        errors = output.get("errors", {}) or {}

        if not results:
            hint = "、".join(databases) or "科学数据库"
            msg = f"在 {hint} 中未找到与“{query}”相关的结果。"
            if errors:
                msg += "\n\n部分来源返回错误：" + "; ".join(
                    f"{k}: {v}" for k, v in errors.items() if k != "_"
                )
            return msg

        lines = [
            f"检索到 {len(results)} 条结果（来源：{', '.join(databases) or '多库'}）：\n"
        ]
        for idx, hit in enumerate(results, start=1):
            if not isinstance(hit, dict):
                continue
            title = hit.get("title") or "Untitled"
            source = hit.get("source") or ""
            url = hit.get("url") or ""
            snippet = (hit.get("snippet") or "").strip().replace("\n", " ")
            if len(snippet) > 240:
                snippet = snippet[:240] + "…"
            published = hit.get("published") or ""
            meta = " · ".join(x for x in [source, published] if x)
            head = f"{idx}. **{title}**"
            if meta:
                head += f"  _{meta}_"
            lines.append(head)
            if snippet:
                lines.append(f"   {snippet}")
            if url:
                lines.append(f"   {url}")
        if errors:
            failed = [k for k in errors if k != "_"]
            if failed:
                lines.append("\n_部分来源失败： " + ", ".join(failed) + "_")
        return "\n".join(lines)

    @staticmethod
    def format_pubmed_fetch(
        output: Dict[str, Any],
        tool_inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format a fetched PubMed article into a readable summary."""
        # `pubmed_fetch` returns the article directly, not wrapped in an `articles` list.
        if isinstance(output, dict) and output.get("articles"):
            article = output["articles"][0]
        elif isinstance(output, dict) and output.get("pmid"):
            article = output
        else:
            return "未获取到 PubMed 文章详情。"
        if not isinstance(article, dict):
            return "PubMed 返回格式异常。"
        title = article.get("title", "未知标题") or "未知标题"
        abstract = article.get("abstract", "") or ""
        pmid = article.get("pmid", "") or ""
        pmid_link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
        lines = [f"**{title}**"]
        if pmid:
            lines.append(f"PMID: [{pmid}]({pmid_link})")
        if abstract:
            lines.append(f"\n{abstract}")
        return "\n".join(lines)

    def format_extra_context(self) -> str:
        """Render CBKB/semantic-memory enrichment into a short project context string."""
        if not self._runner._extra_context:
            return ""
        parts: List[str] = []
        snippets = self._runner._extra_context.get("memory_snippets") or []
        if snippets:
            parts.append(
                "Relevant memory snippets:\n"
                + "\n".join(f"- {s}" for s in snippets[:3])
            )
        experiments = self._runner._extra_context.get("recent_experiments") or []
        if experiments:
            parts.append(
                "Recent experiments:\n"
                + "\n".join(
                    f"- {e.get('bundle_id', '')}: {e.get('summary', '')}"
                    for e in experiments[:3]
                )
            )
        sops = self._runner._extra_context.get("recent_sops") or []
        if sops:
            parts.append(
                "Relevant SOPs:\n"
                + "\n".join(
                    f"- {s.get('name', '')} ({s.get('category', '')})" for s in sops[:3]
                )
            )
        anomalies = self._runner._extra_context.get("recent_anomalies") or []
        if anomalies:
            parts.append(
                "Recent anomalies:\n"
                + "\n".join(
                    f"- {a.get('phase_type', '')}: {a.get('summary', '')}"
                    for a in anomalies[:3]
                )
            )
        return "\n\n".join(parts)
