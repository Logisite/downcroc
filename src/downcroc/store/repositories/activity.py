from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from downcroc.domain.activity import (
    ACTIVITY_FIELDS,
    AccountActivity,
    ActivitySummary,
    ActivityTotals,
    DailyActivity,
    HourlyActivity,
)
from downcroc.store.db.models import (
    ActivityDailyRow,
    ActivityHourlyRow,
)


def hour_key(moment: datetime) -> str:
    return moment.astimezone().strftime("%Y-%m-%dT%H:00:00")


def day_key(moment: datetime) -> str:
    return moment.astimezone().strftime("%Y-%m-%d")


def _totals(row: ActivityHourlyRow | ActivityDailyRow) -> ActivityTotals:
    return ActivityTotals(
        sent=row.sent,
        failed=row.failed,
        received=row.received,
        replies=row.replies,
        bounces=row.bounces,
        suppressed=row.suppressed,
    )


def _values(deltas: dict[str, int]) -> dict[str, int]:
    unknown = set(deltas) - set(ACTIVITY_FIELDS)
    if unknown:
        raise ValueError(f"unknown activity field {min(unknown)}")
    return {field: int(deltas.get(field, 0)) for field in ACTIVITY_FIELDS}


class ActivityRepo:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def add(
        self,
        account_id: str,
        moment: datetime,
        deltas: dict[str, int],
        *,
        quota_limit: int | None = None,
    ) -> None:
        values = _values(deltas)
        hour_start = hour_key(moment)
        day = day_key(moment)
        with self._sessions.begin() as session:
            hourly = sqlite_insert(ActivityHourlyRow).values(
                account_id=account_id,
                hour_start=hour_start,
                **values,
            )
            hourly = hourly.on_conflict_do_update(
                index_elements=[
                    ActivityHourlyRow.account_id,
                    ActivityHourlyRow.hour_start,
                ],
                set_={
                    field: getattr(ActivityHourlyRow, field) + values[field]
                    for field in ACTIVITY_FIELDS
                    if values[field]
                },
            )
            session.execute(hourly)
            daily = sqlite_insert(ActivityDailyRow).values(
                account_id=account_id,
                day=day,
                quota_limit=quota_limit or 0,
                **values,
            )
            updated = {
                field: getattr(ActivityDailyRow, field) + values[field]
                for field in ACTIVITY_FIELDS
                if values[field]
            }
            if quota_limit is not None:
                updated["quota_limit"] = quota_limit
            daily = daily.on_conflict_do_update(
                index_elements=[ActivityDailyRow.account_id, ActivityDailyRow.day],
                set_=updated,
            )
            session.execute(daily)

    def summary(
        self,
        start_day: str,
        end_day: str,
        account_id: str | None = None,
    ) -> ActivitySummary:
        query = (
            select(
                ActivityDailyRow.account_id,
                func.sum(ActivityDailyRow.sent),
                func.sum(ActivityDailyRow.failed),
                func.sum(ActivityDailyRow.received),
                func.sum(ActivityDailyRow.replies),
                func.sum(ActivityDailyRow.bounces),
                func.sum(ActivityDailyRow.suppressed),
            )
            .where(
                ActivityDailyRow.day >= start_day,
                ActivityDailyRow.day <= end_day,
            )
            .group_by(ActivityDailyRow.account_id)
            .order_by(ActivityDailyRow.account_id)
        )
        if account_id is not None:
            query = query.where(ActivityDailyRow.account_id == account_id)
        with self._sessions() as session:
            rows = session.execute(query).all()
        accounts = tuple(
            AccountActivity(
                account_id=row[0],
                totals=ActivityTotals(
                    sent=int(row[1] or 0),
                    failed=int(row[2] or 0),
                    received=int(row[3] or 0),
                    replies=int(row[4] or 0),
                    bounces=int(row[5] or 0),
                    suppressed=int(row[6] or 0),
                ),
            )
            for row in rows
        )
        total = ActivityTotals(
            sent=sum(item.totals.sent for item in accounts),
            failed=sum(item.totals.failed for item in accounts),
            received=sum(item.totals.received for item in accounts),
            replies=sum(item.totals.replies for item in accounts),
            bounces=sum(item.totals.bounces for item in accounts),
            suppressed=sum(item.totals.suppressed for item in accounts),
        )
        return ActivitySummary(accounts=accounts, total=total)

    def hourly(
        self,
        start_hour: str,
        end_hour: str,
        account_id: str | None = None,
    ) -> tuple[HourlyActivity, ...]:
        query = (
            select(ActivityHourlyRow)
            .where(
                ActivityHourlyRow.hour_start >= start_hour,
                ActivityHourlyRow.hour_start < end_hour,
            )
            .order_by(ActivityHourlyRow.hour_start, ActivityHourlyRow.account_id)
        )
        if account_id is not None:
            query = query.where(ActivityHourlyRow.account_id == account_id)
        with self._sessions() as session:
            rows = session.scalars(query)
            return tuple(
                HourlyActivity(
                    account_id=row.account_id,
                    hour_start=row.hour_start,
                    totals=_totals(row),
                )
                for row in rows
            )

    def daily(
        self,
        start_day: str,
        end_day: str,
        account_id: str | None = None,
    ) -> tuple[DailyActivity, ...]:
        query = (
            select(ActivityDailyRow)
            .where(
                ActivityDailyRow.day >= start_day,
                ActivityDailyRow.day <= end_day,
            )
            .order_by(ActivityDailyRow.day, ActivityDailyRow.account_id)
        )
        if account_id is not None:
            query = query.where(ActivityDailyRow.account_id == account_id)
        with self._sessions() as session:
            rows = session.scalars(query)
            return tuple(
                DailyActivity(
                    account_id=row.account_id,
                    day=row.day,
                    totals=_totals(row),
                    quota_limit=row.quota_limit,
                )
                for row in rows
            )

    def stored_sent(self, start_day: str, end_day: str) -> int:
        with self._sessions() as session:
            value = session.scalar(
                select(func.sum(ActivityDailyRow.sent)).where(
                    ActivityDailyRow.day >= start_day,
                    ActivityDailyRow.day <= end_day,
                )
            )
            return int(value or 0)

    def suppressed(
        self,
        since_day: str | None,
    ) -> tuple[dict[tuple[str, str], int], dict[tuple[str, str], int]]:
        hourly_query = select(
            ActivityHourlyRow.account_id,
            ActivityHourlyRow.hour_start,
            ActivityHourlyRow.suppressed,
        )
        daily_query = select(
            ActivityDailyRow.account_id,
            ActivityDailyRow.day,
            ActivityDailyRow.suppressed,
        )
        if since_day is not None:
            hourly_query = hourly_query.where(
                ActivityHourlyRow.hour_start >= f"{since_day}T00:00:00"
            )
            daily_query = daily_query.where(ActivityDailyRow.day >= since_day)
        with self._sessions() as session:
            hourly = {
                (row[0], row[1]): int(row[2])
                for row in session.execute(hourly_query)
                if row[2]
            }
            daily = {
                (row[0], row[1]): int(row[2])
                for row in session.execute(daily_query)
                if row[2]
            }
        return hourly, daily

    def replace(
        self,
        since_day: str | None,
        hourly: dict[tuple[str, str], dict[str, int]],
        daily: dict[tuple[str, str], dict[str, int]],
    ) -> int:
        with self._sessions.begin() as session:
            _delete_activity(session, since_day)
            for (account_id, hour_start), values in hourly.items():
                session.add(
                    ActivityHourlyRow(
                        account_id=account_id,
                        hour_start=hour_start,
                        **_values(values),
                    )
                )
            for (account_id, day), values in daily.items():
                fields = dict(values)
                quota_limit = int(fields.pop("quota_limit", 0))
                session.add(
                    ActivityDailyRow(
                        account_id=account_id,
                        day=day,
                        quota_limit=quota_limit,
                        **_values(fields),
                    )
                )
        return len(hourly) + len(daily)

    def prune_hourly(self, cutoff_hour: str) -> int:
        with self._sessions.begin() as session:
            result = session.execute(
                delete(ActivityHourlyRow).where(
                    ActivityHourlyRow.hour_start < cutoff_hour
                )
            )
            return int(result.rowcount or 0)

    def prune_daily(self, cutoff_day: str) -> int:
        with self._sessions.begin() as session:
            result = session.execute(
                delete(ActivityDailyRow).where(ActivityDailyRow.day < cutoff_day)
            )
            return int(result.rowcount or 0)


def _delete_activity(session: Session, since_day: str | None) -> None:
    hourly = delete(ActivityHourlyRow)
    daily = delete(ActivityDailyRow)
    if since_day is not None:
        hourly = hourly.where(ActivityHourlyRow.hour_start >= f"{since_day}T00:00:00")
        daily = daily.where(ActivityDailyRow.day >= since_day)
    session.execute(hourly)
    session.execute(daily)
