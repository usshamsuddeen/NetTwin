"""Bridge between the simulator ResponseAgent and the AWS actuator.

When an action is applied in the simulator, the bridge can optionally mirror it
into real AWS infrastructure via ``AWSActuator``."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from nettwin.actuation.executor import AWSActuator

log = logging.getLogger("nettwin.actuation")


class ActuationBridge:
    """Async façade used by the ResponseAgent to trigger AWS changes."""

    def __init__(self, actuator: AWSActuator) -> None:
        self.actuator = actuator

    async def apply(self, action_id: str, kind: str, params: dict[str, Any]) -> None:
        if not self.actuator.settings.actuation.enabled:
            return
        result = await self.actuator.execute(action_id, kind, params)
        if result.success:
            log.info("aws actuation succeeded for %s: %s", action_id, result.changes)
        else:
            log.warning("aws actuation failed for %s: %s", action_id, result.error)

    def sync_callback(self, action_id: str, kind: str, params: dict[str, Any]) -> None:
        """Fire-and-forget wrapper for the synchronous ResponseAgent path."""
        try:
            asyncio.create_task(self.apply(action_id, kind, params))
        except RuntimeError:
            # No running event loop in test / offline contexts.
            pass
