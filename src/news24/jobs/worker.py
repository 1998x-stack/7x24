"""Single-runner job worker with bounded execution and explicit failure states."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import httpx

from news24.ingestion.service import run_ingestion
from news24.jobs.scheduler import ScheduleStore
from news24.jobs.store import JobStore
from news24.observability.health import probe_sina
from news24.reporting.service import generate_daily_report
from news24.sources.sina.async_client import SinaFeedClient
from news24.storage.database import SQLiteNewsStore

JobHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class JobWorker:
    """One job at a time. No external queue or distributed leader is required."""

    def __init__(
        self,
        store: SQLiteNewsStore,
        *,
        handlers: dict[str, JobHandler] | None = None,
        clock: Callable[[], datetime] | None = None,
        owner: str | None = None,
    ) -> None:
        self.store = store
        store.migrate()
        self.jobs = JobStore(store)
        self.schedules = ScheduleStore(self.jobs)
        self.handlers = handlers or {}
        self.clock = clock or (lambda: datetime.now(UTC))
        self.owner = owner or uuid4().hex

    async def _default_handler(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        if kind == "report":
            report_date = date.fromisoformat(str(payload["report_date"]))
            return generate_daily_report(
                self.store,
                report_date,
                timezone=str(payload.get("timezone", "Asia/Shanghai")),
                now=self.clock(),
            )

        if kind in ("collect", "probe"):
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=False,
                headers={"Referer": "https://finance.sina.com.cn/7x24/"},
            ) as http:
                source = SinaFeedClient(
                    http, delay=float(payload.get("delay", 0.5))
                )
                if kind == "probe":
                    return await probe_sina(
                        self.store, source, now=self.clock(),
                        max_age_seconds=int(payload.get("max_age_seconds", 14400)),
                    )
                return await run_ingestion(
                    self.store, source,
                    category=str(payload.get("category", "all")),
                    max_pages=int(payload.get("max_pages", 10)),
                    page_size=int(payload.get("page_size", 50)),
                )
        # Intentionally do not pretend model-based analysis exists in V0.4.
        raise NotImplementedError("analyze executor requires a V0.5 plugin")

    async def run_once(self, *, lease_seconds: int = 180) -> dict[str, Any]:
        now = self.clock()
        self.jobs.recover_expired(now=now)
        self.schedules.tick(now=now)
        job = self.jobs.claim(self.owner, now=now, lease_seconds=lease_seconds)
        if job is None:
            return {"state": "IDLE", "owner": self.owner}
        try:
            async def execute() -> dict[str, Any]:
                handler = self.handlers.get(str(job["kind"]))
                if handler is not None:
                    return await handler(dict(job["payload"]))
                return await self._default_handler(str(job["kind"]), dict(job["payload"]))

            result = await asyncio.wait_for(
                execute(), timeout=max(1.0, float(lease_seconds - 5))
            )
            if result.get("status") == "INCOMPLETE":
                raise RuntimeError("source pagination incomplete; retrying without advancing cursor")
            if job["kind"] == "probe" and result.get("status") != "OK":
                raise RuntimeError(f"source probe unhealthy: {result.get('status')}")
            state = self.jobs.succeed(job, result, now=self.clock())
            return {"state": state, "job_key": job["key"], "result": result}
        except Exception as exc:
            state = self.jobs.fail(job, exc, now=self.clock())
            return {
                "state": state, "job_key": job["key"],
                "error": f"{type(exc).__name__}: {exc}"[:1024],
            }

    async def serve(self, *, poll_seconds: float = 5.0, max_jobs: int | None = None) -> int:
        if poll_seconds < 0.1 or (max_jobs is not None and max_jobs < 1):
            raise ValueError("poll_seconds must be >=0.1 and max_jobs positive")
        count = 0
        while True:
            output = await self.run_once()
            if output["state"] != "IDLE":
                count += 1
            if max_jobs is not None and count >= max_jobs:
                return count
            await asyncio.sleep(poll_seconds)
