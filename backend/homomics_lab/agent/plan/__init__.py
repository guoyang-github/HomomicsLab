"""PlanEngine — state-driven analysis plan generation.

Import submodules directly (e.g. ``from homomics_lab.agent.plan.engine import
PlanEngine``) to avoid pulling in the full planning graph at package load time.
"""

# Intentionally empty: no eager re-exports.  The planning submodules have
# interdependencies that can create circular imports if they are all loaded
# through this package __init__.  Keeping this file lightweight lets callers
# import only what they need.
