from __future__ import annotations

from typing import Any

from downcroc.extensions.broker import Broker, Invocation
from downcroc.extensions.capabilities.common import dump, limit, offset, require


def register_inspection(broker: Broker) -> None:
    names = (
        "account.list",
        "account.get",
        "account.audit",
        "provider.list",
        "provider.get",
        "provider.declaration",
        "transport.list",
        "transport.get",
        "transport.history",
        "message.list",
        "message.get",
        "message.search",
        "thread.list",
        "thread.get",
        "thread.timeline",
        "job.list",
        "job.get",
        "job.attempts",
        "job.artifacts",
        "batch.list",
        "batch.get",
        "batch.thread",
        "batch.followups",
        "batch.suppression",
        "failed.list",
        "failed.get",
        "followup.status",
        "followup.outlook",
        "followup.due",
        "stats.query",
        "logs.query",
        "config.get",
        "config.schema",
        "service.status",
        "service.health",
        "doctor.capacity",
        "backfill.status",
        "holds.list",
        "quota.get",
        "policy.get",
        "policy.effective",
        "vault.status",
        "update.status",
        "events.query",
    )
    broker.register(names, inspect)


def inspect(inv: Invocation, params: dict[str, Any]) -> Any:
    name = inv.capability
    services = inv.services
    if name == "account.list":
        return dump(
            services.accounts.list(archived=bool(params.get("archived", False)))
        )
    if name == "account.get":
        return dump(services.accounts.get(require(inv, "account")))
    if name == "account.audit":
        return dump(services.accounts.deletion_preview(require(inv, "account")))
    if name.startswith("provider."):
        return provider(inv)
    if name.startswith("transport."):
        return transport(inv)
    if name.startswith("message."):
        return message(inv)
    if name.startswith("thread."):
        return thread(inv)
    if name.startswith("job."):
        return job(inv)
    if name.startswith("batch."):
        return batch(inv)
    if name.startswith("failed."):
        return failed(inv)
    if name.startswith("followup."):
        return followup(inv)
    if name == "stats.query":
        return stats(inv)
    if name == "logs.query":
        return logs(inv)
    if name == "config.get":
        return services.config.snapshot()
    if name == "config.schema":
        return services.config.fields()
    if name == "service.status":
        return {"ok": True, "daemon": "running"}
    if name == "service.health":
        return dump(services.doctor.inbound())
    if name == "doctor.capacity":
        return dump(services.doctor.capacity())
    if name == "backfill.status":
        return {"enabled": inv.settings is not None}
    if name == "holds.list":
        return dump(services.holds.status_block())
    if name == "quota.get":
        return _quota(inv)
    if name == "policy.get":
        return dump(services.policy_overrides.account_view(require(inv, "account")))
    if name == "policy.effective":
        return dump(
            services.policy.effective(services.accounts.get(require(inv, "account")))
        )
    if name == "vault.status":
        return dump(services.vault.status())
    if name == "update.status":
        return {"current": services.config.snapshot().get("version", "")}
    if name == "events.query":
        return dump(services.events.recent(str(params.get("prefix", "")), limit(inv)))
    raise ValueError(f"unsupported inspection capability {name}")


def provider(inv: Invocation) -> Any:
    services = inv.services
    name = inv.capability
    if name == "provider.list":
        return dump(services.providers.list())
    if name == "provider.get":
        return dump(services.providers.get(require(inv, "provider")))
    return {"id": require(inv, "provider"), "declaration": ""}


def transport(inv: Invocation) -> Any:
    services = inv.services
    name = inv.capability
    if name == "transport.list":
        return dump(services.transports.list(require(inv, "account")))
    if name == "transport.get":
        return dump(
            services.transports.get(require(inv, "account"), require(inv, "transport"))
        )
    return dump(services.transports.history(require(inv, "transport")))


def message(inv: Invocation) -> Any:
    services = inv.services
    name = inv.capability
    if name == "message.get":
        return dump(services.messages.get_message(require(inv, "message")))
    if name in {"message.list", "message.search"}:
        return dump(
            services.messages.list_messages(
                account_id=inv.param("account"),
                thread_id=inv.param("thread"),
                reply_state=inv.param("reply_state"),
                since=inv.param("since"),
                until=inv.param("until"),
                limit=limit(inv),
                offset=offset(inv),
                newest_first=bool(inv.param("newest_first", True)),
            )
        )
    return {}


def thread(inv: Invocation) -> Any:
    services = inv.services
    name = inv.capability
    if name == "thread.list":
        return dump(
            services.messages.list_threads(
                account_id=inv.param("account"),
                batch_id=inv.param("batch"),
                limit=limit(inv),
                offset=offset(inv),
            )
        )
    return dump(services.messages.get_thread(require(inv, "thread")))


def job(inv: Invocation) -> Any:
    services = inv.services
    name = inv.capability
    if name == "job.get":
        return dump(services.jobs.get(require(inv, "job")))
    if name == "job.attempts":
        return dump(services.send_attempts.list_for_job(require(inv, "job")))
    return {"job": require(inv, "job"), "artifacts": []}


def batch(inv: Invocation) -> Any:
    services = inv.services
    name = inv.capability
    if name == "batch.get":
        return dump(services.batches.detail(require(inv, "batch")))
    if name == "batch.thread":
        return {"batch": require(inv, "batch"), "threads": []}
    if name == "batch.followups":
        return dump(services.followups.status(require(inv, "batch")))
    return dump(services.batches.suppression_preview(require(inv, "batch")))


def failed(inv: Invocation) -> Any:
    services = inv.services
    if inv.capability == "failed.list":
        return dump(services.failures.list(limit(inv), offset(inv)))
    return {"failure": require(inv, "failure")}


def followup(inv: Invocation) -> Any:
    services = inv.services
    name = inv.capability
    if name == "followup.status":
        return dump(services.followups.status(require(inv, "batch")))
    if name == "followup.outlook":
        return dump(services.followups.outlook(_due_days(inv)))
    return dump(services.followups.outlook(7))


def stats(inv: Invocation) -> Any:
    services = inv.services
    kind = str(inv.param("kind", "summary"))
    start = inv.param("from")
    end = inv.param("to")
    account = inv.param("account")
    if kind == "hourly":
        return dump(services.stats.hourly(start, end, account))
    if kind == "daily":
        return dump(services.stats.daily(start, end, account))
    if kind == "accounts":
        return dump(services.stats.accounts_for(start, end, account))
    if kind == "batches":
        return dump(services.stats.batches_for(start, end, account))
    return dump(services.stats.summary(start, end, account))


def logs(inv: Invocation) -> Any:
    events = inv.services.events
    prefix = str(inv.param("event", ""))
    return dump(events.recent(prefix, limit(inv)))


def _due_days(inv: Invocation) -> int | None:
    value = inv.param("due")
    if value in (None, "", "all"):
        return None
    return int(str(value).rstrip("d"))


def _quota(inv: Invocation) -> Any:
    account = inv.services.accounts.get(require(inv, "account"))
    policy = inv.services.policy.effective(account)
    day = inv.services.policy.day()
    used, reserved = inv.services.quota.status(account.id, day)
    limit = policy.daily_allowance
    return {
        "account": account.id,
        "day": day,
        "limit": limit,
        "used": used,
        "reserved": reserved,
        "remaining": max(0, limit - used - reserved),
    }
