"""Business-logic services.

Temporary home for behaviour that needs collaborators (registries, the
conversion graph) and therefore does not belong on the pure Pydantic models.
This package will be shaped properly in a later pass; for now it exposes
plain functions that take the relevant models/registries as arguments and
are called from the adapters and calculator.
"""
