"""Eating-log HTML report over resolved logs (no planning, no batches).

``meal_prep.logbook.report`` renders a ``LogWeek`` to standalone HTML.
"""

from __future__ import annotations

from meal_prep.logbook.report import render_log_week, render_log_week_page

__all__ = ["render_log_week", "render_log_week_page"]
