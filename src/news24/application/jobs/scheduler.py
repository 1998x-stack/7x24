"""Persistent interval/daily schedules with a bounded skip-missed policy.

At most one current occurrence is enqueued per schedule per tick. Missed
intervals are not replayed in a storm when a process comes back online.
"""

import json
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from news24.infrastructure.sqlite.job_store import JobStore, utc_time


def _daily_at(day: date, hhmm: str, timezone: str) -> datetime:
    hour, minute = (int(part) for part in hhmm.split(":"))
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("daily schedule must use HH:MM")
    return datetime.combine(day, time(hour, minute), ZoneInfo(timezone))


class ScheduleStore:
    def __init__(self, jobs: JobStore) -> None:
        self.jobs = jobs
        self.conn = jobs.conn

    def install_interval(
        self,
        schedule_id: str,
        kind: str,
        payload: dict[str, Any],
        *,
        seconds: int,
        now: datetime,
    ) -> None:
        if not schedule_id or seconds < 30:
            raise ValueError("schedule id is required; interval must be at least 30 seconds")
        if kind not in ("collect", "probe"):
            raise ValueError("interval supports only collect/probe")
        self.conn.execute(
            """INSERT OR IGNORE INTO job_schedules
               (schedule_id, kind, payload_json, cadence, interval_seconds,
                local_time, timezone, next_due_at)
               VALUES (?, ?, ?, 'interval', ?, NULL, 'UTC', ?)""",
            (schedule_id, kind, json.dumps(payload, sort_keys=True),
             seconds, utc_time(now)),
        )

    def install_daily(
        self,
        schedule_id: str,
        kind: str,
        payload: dict[str, Any],
        *,
        hhmm: str,
        timezone: str,
        now: datetime,
    ) -> None:
        if not schedule_id or kind != "report":
            raise ValueError("daily schedule supports only report")
        zone = ZoneInfo(timezone)
        local = now.astimezone(zone)
        due = _daily_at(local.date(), hhmm, timezone)
        if due <= local:
            due = _daily_at(local.date() + timedelta(days=1), hhmm, timezone)
        self.conn.execute(
            """INSERT OR IGNORE INTO job_schedules
               (schedule_id, kind, payload_json, cadence, interval_seconds,
                local_time, timezone, next_due_at)
               VALUES (?, ?, ?, 'daily', NULL, ?, ?, ?)""",
            (schedule_id, kind, json.dumps(payload, sort_keys=True),
             hhmm, timezone, utc_time(due)),
        )

    def tick(self, *, now: datetime) -> int:
        timestamp = utc_time(now)
        count = 0
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            schedules = self.conn.execute(
                """SELECT * FROM job_schedules
                   WHERE enabled=1 AND next_due_at<=?
                   ORDER BY next_due_at, schedule_id""",
                (timestamp,),
            ).fetchall()
            for schedule in schedules:
                due = datetime.fromisoformat(schedule["next_due_at"])
                payload = json.loads(schedule["payload_json"])
                if schedule["cadence"] == "interval":
                    seconds = int(schedule["interval_seconds"])
                    missed = max(0, int((now - due).total_seconds() // seconds))
                    occurrence = due + timedelta(seconds=missed * seconds)
                    following = occurrence + timedelta(seconds=seconds)
                else:
                    zone = str(schedule["timezone"])
                    hhmm = str(schedule["local_time"])
                    local = now.astimezone(ZoneInfo(zone))
                    occurrence = _daily_at(local.date(), hhmm, zone)
                    if occurrence > local:
                        occurrence = _daily_at(
                            local.date() - timedelta(days=1), hhmm, zone
                        )
                    following = _daily_at(
                        local.date() + timedelta(days=1), hhmm, zone
                    )
                    if schedule["kind"] == "report":
                        payload["report_date"] = (
                            occurrence.date() - timedelta(days=1)
                        ).isoformat()
                        payload["timezone"] = zone

                key = f"{schedule['schedule_id']}:{utc_time(occurrence)}"
                if self.jobs.enqueue(key, str(schedule["kind"]), payload, now=now):
                    count += 1
                self.conn.execute(
                    """UPDATE job_schedules SET next_due_at=?
                       WHERE schedule_id=?""",
                    (utc_time(following), schedule["schedule_id"]),
                )
            self.conn.execute("COMMIT")
            return count
        except Exception:
            if self.conn.in_transaction:
                self.conn.execute("ROLLBACK")
            raise
