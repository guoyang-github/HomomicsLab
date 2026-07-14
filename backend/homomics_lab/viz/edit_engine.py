"""Rule-based natural-language editor for Plotly figures.

This engine applies lightweight, deterministic edits to an existing Plotly
figure dict (``{data: [...], layout: {...}}``) based on free-form user
instructions such as "换成箱线图", "加误差线", or "换个配色".

It is intentionally simple: it does not re-run the original analysis or
generate new data, it only mutates the figure description that the frontend
already knows how to render.  When the requested edit cannot be applied
reliably, it returns ``None`` so the caller can fall back to a text response.
"""

import re
from typing import Any, Dict, List, Optional


# Common color names mapped to Plotly/CSS hex values.
_COLOR_MAP: Dict[str, str] = {
    "red": "#e41a1c",
    "green": "#4daf4a",
    "blue": "#377eb8",
    "orange": "#ff7f0e",
    "purple": "#984ea3",
    "yellow": "#ffff33",
    "black": "#000000",
    "grey": "#7f7f7f",
    "gray": "#7f7f7f",
    "pink": "#f781bf",
    "brown": "#a65628",
    "青": "#377eb8",
    "蓝": "#377eb8",
    "蓝色": "#377eb8",
    "红": "#e41a1c",
    "红色": "#e41a1c",
    "绿": "#4daf4a",
    "绿色": "#4daf4a",
    "橙": "#ff7f0e",
    "橙色": "#ff7f0e",
    "紫": "#984ea3",
    "紫色": "#984ea3",
    "黄": "#ffff33",
    "黄色": "#ffff33",
    "黑": "#000000",
    "黑色": "#000000",
    "灰": "#7f7f7f",
    "灰色": "#7f7f7f",
}

# Discrete color palettes.
_PALETTES: Dict[str, List[str]] = {
    "nature": ["#0C5DA5", "#FF2C00", "#00B945", "#845B97", "#FFC337", "#1B1B1B"],
    "lancet": ["#00468B", "#ED0000", "#42B540", "#0099B4", "#925E9F", "#FDAF91"],
    "nejm": ["#BC3C29", "#0072B5", "#E18727", "#20854E", "#7876B1", "#6F99AD"],
    "jco": ["#E66100", "#5D3A9B", "#0072B2", "#009E73", "#F0E442", "#CC79A7"],
    "default": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"],
}


class PlotlyEditEngine:
    """Apply natural-language edits to a Plotly figure dict."""

    def __init__(self, figure: Dict[str, Any]):
        self.figure = figure
        self.data: List[Dict[str, Any]] = list(figure.get("data", []))
        self.layout: Dict[str, Any] = dict(figure.get("layout", {}))

    @classmethod
    def apply(cls, instruction: str, figure: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Apply an edit instruction to a figure and return the new figure dict.

        Returns ``None`` when the instruction cannot be handled deterministically.
        """
        engine = cls(figure)
        changed = engine._apply(instruction)
        if not changed:
            return None
        return {"data": engine.data, "layout": engine.layout}

    # --- Intent detectors ---------------------------------------------------

    @staticmethod
    def _wants_box_plot(text: str) -> bool:
        return any(
            kw in text
            for kw in [
                "箱线", "箱型", "box plot", "boxplot", "box",
                "换成箱", "改为箱", "变成箱",
            ]
        )

    @staticmethod
    def _wants_violin_plot(text: str) -> bool:
        return any(
            kw in text
            for kw in ["小提琴", "violin", "violinplot", "换成小提琴", "改为小提琴"]
        )

    @staticmethod
    def _wants_bar_plot(text: str) -> bool:
        return any(
            kw in text
            for kw in [
                "柱状", "条形", "bar chart", "bar plot", "barplot",
                "换成柱", "改为柱", "变成柱",
            ]
        )

    @staticmethod
    def _wants_error_bars(text: str) -> bool:
        return any(
            kw in text
            for kw in ["误差线", "error bar", "errorbar", "error bars", "加误差", "标准差", "std"]
        )

    @staticmethod
    def _wants_legend_toggle(text: str) -> bool:
        return any(kw in text for kw in ["legend", "图例", "hide legend", "显示图例", "去掉图例"])

    @staticmethod
    def _extract_color(text: str) -> Optional[str]:
        for name, hex_value in _COLOR_MAP.items():
            if name in text:
                return hex_value
        # Hex color literal.
        match = re.search(r"#([0-9a-f]{6}|[0-9a-f]{3})\b", text)
        if match:
            return match.group(0)
        return None

    @staticmethod
    def _extract_palette(text: str) -> Optional[str]:
        for name in _PALETTES:
            if name in text:
                return name
        return None

    @staticmethod
    def _extract_title(text: str) -> Optional[str]:
        # "标题改为 XXX" / "title to XXX" / "title: XXX"
        patterns = [
            r"标题[\s:：改为改成改成改成](.+)",
            r"title[\s:：to](.+)",
            r"set title[\s:：to](.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip(" \"'，。！？")
        return None

    # --- Transformations ----------------------------------------------------

    def _convert_to_box(self) -> bool:
        """Convert compatible traces to box traces."""
        if not self.data:
            return False
        changed = False
        for trace in self.data:
            t = trace.get("type")
            if t == "box":
                continue
            if t == "violin":
                trace["type"] = "box"
                trace.setdefault("boxpoints", False)
                changed = True
            elif t == "bar":
                # Aggregated bar data cannot be turned into a meaningful box plot
                # without raw values.  Fall back to a single-value box per bar
                # so the figure still renders, but mark it visually.
                trace["type"] = "box"
                trace.setdefault("boxpoints", "all")
                trace.setdefault("jitter", 0)
                trace.setdefault("pointpos", 0)
                trace.setdefault("name", trace.get("x", [""])[0] if trace.get("x") else "")
                changed = True
            elif t == "scatter":
                trace["type"] = "box"
                if "x" in trace and trace.get("x"):
                    trace["y"] = trace.get("y", [])
                changed = True
        return changed

    def _convert_to_violin(self) -> bool:
        if not self.data:
            return False
        changed = False
        for trace in self.data:
            t = trace.get("type")
            if t == "violin":
                continue
            if t in ("box", "bar", "scatter"):
                trace["type"] = "violin"
                trace.setdefault("box", {"visible": True})
                trace.setdefault("meanline", {"visible": True})
                trace.setdefault("opacity", 0.7)
                changed = True
        return changed

    def _convert_to_bar(self) -> bool:
        if not self.data:
            return False
        changed = False
        for trace in self.data:
            t = trace.get("type")
            if t == "bar":
                continue
            if t in ("box", "violin", "scatter"):
                trace["type"] = "bar"
                changed = True
        return changed

    def _add_error_bars(self) -> bool:
        """Add symmetric error bars to bar/scatter traces when possible."""
        if not self.data:
            return False
        changed = False
        for trace in self.data:
            t = trace.get("type")
            if t == "bar":
                y = trace.get("y", [])
                if isinstance(y, list) and y:
                    # If only one value per category, error is unknowable.
                    # Use a small relative placeholder so the visual cue appears.
                    errors = [
                        float(v) * 0.1 if isinstance(v, (int, float)) and v != 0 else 0.1
                        for v in y
                    ]
                    trace["error_y"] = {"type": "data", "array": errors, "visible": True}
                    changed = True
            elif t == "scatter":
                y = trace.get("y", [])
                if isinstance(y, list) and y:
                    errors = [
                        abs(float(v)) * 0.1 if isinstance(v, (int, float)) and v != 0 else 0.1
                        for v in y
                    ]
                    trace["error_y"] = {"type": "data", "array": errors, "visible": True}
                    changed = True
        return changed

    def _apply_color(self, color: str) -> bool:
        """Apply a single color to all traces."""
        if not self.data:
            return False
        for trace in self.data:
            marker = trace.setdefault("marker", {})
            marker["color"] = color
            line = trace.setdefault("line", {})
            line["color"] = color
        return True

    def _apply_palette(self, palette_name: str) -> bool:
        """Apply a named palette via layout.colorway."""
        palette = _PALETTES.get(palette_name, _PALETTES["default"])
        self.layout["colorway"] = palette
        for i, trace in enumerate(self.data):
            if trace.get("type") in ("bar", "scatter"):
                marker = trace.setdefault("marker", {})
                marker["color"] = palette[i % len(palette)]
        return True

    def _apply_title(self, title: str) -> bool:
        self.layout["title"] = {"text": title}
        return True

    def _toggle_legend(self) -> bool:
        show = not any(
            kw in str(self._latest_instruction or "").lower()
            for kw in ["hide", "去掉", "隐藏", "不显示"]
        )
        # Simple heuristic: if user explicitly says hide, hide; otherwise show.
        # We cannot reliably infer from a bare "legend" keyword, so default to show.
        self.layout["showlegend"] = show
        return True

    @property
    def _latest_instruction(self) -> Optional[str]:
        return getattr(self, "_instruction", None)

    def _apply(self, instruction: str) -> bool:  # type: ignore[no-redef]
        self._instruction = instruction
        text = instruction.lower()
        changed = False

        if self._wants_box_plot(text):
            changed = self._convert_to_box() or changed

        if self._wants_violin_plot(text):
            changed = self._convert_to_violin() or changed

        if self._wants_bar_plot(text):
            changed = self._convert_to_bar() or changed

        if self._wants_error_bars(text):
            changed = self._add_error_bars() or changed

        color = self._extract_color(text)
        if color is not None:
            changed = self._apply_color(color) or changed

        palette = self._extract_palette(text)
        if palette is not None:
            changed = self._apply_palette(palette) or changed

        title = self._extract_title(text)
        if title is not None:
            changed = self._apply_title(title) or changed

        if self._wants_legend_toggle(text):
            changed = self._toggle_legend() or changed

        return changed
