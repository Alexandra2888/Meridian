"""In-memory CRM client backed by `app/data/learners.json`.

Used for: eval runs, offline development, and demo fallback if HubSpot has an
incident on demo day. Same `CRMClient` interface as `HubSpotCRMClient`.
"""

from __future__ import annotations

from app.data import learners
from app.schemas.learner import LearnerProfile


class StubCRMClient:
    def __init__(self) -> None:
        self._by_id: dict[str, LearnerProfile] = {
            row["learner_id"]: LearnerProfile(**row) for row in learners()
        }

    async def get_learner(self, learner_id: str) -> LearnerProfile:
        # Fall back to the first stub learner when the requested id is unknown
        # so demos with arbitrary ids never 404.
        if learner_id in self._by_id:
            return self._by_id[learner_id]
        return next(iter(self._by_id.values()))

    async def health(self) -> bool:
        return True
