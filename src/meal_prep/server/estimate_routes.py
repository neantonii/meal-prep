"""AI estimate routes (#141): whether estimates are on, and one estimate.
The client lives in ``meal_prep.server.estimate``; saving the items is an
ordinary free-form add (``diary_routes``)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from meal_prep.server.api_models import EstimatedItemOut, EstimateOut, EstimateRequest
from meal_prep.server.estimate import CachedEstimator, EstimateError

logger = logging.getLogger("meal_prep.server")


def estimate_router(estimator: CachedEstimator | None) -> APIRouter:
    router = APIRouter(prefix="/api/estimate")

    @router.get("")
    def estimate_status() -> dict[str, bool | str | None]:
        """On when the host has an API key; the model it uses."""
        return {
            "available": estimator is not None,
            "model": None if estimator is None else estimator.estimator.model,
        }

    @router.post("")
    def estimate(body: EstimateRequest) -> EstimateOut:
        if estimator is None:
            raise HTTPException(
                status_code=503, detail="AI estimates are off: no API key set"
            )
        try:
            reply = estimator.estimate(body.text)
        except EstimateError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e
        logger.info(
            "estimated %r: %s",
            body.text[:80],
            ", ".join(f"{i.name} {i.kcal:.0f}" for i in reply.items),
        )
        return EstimateOut(
            items=[EstimatedItemOut(**item.model_dump()) for item in reply.items]
        )

    return router
