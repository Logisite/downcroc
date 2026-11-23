from __future__ import annotations

from typing import Any

from downcroc.extensions.broker import Broker, Invocation
from downcroc.extensions.capabilities.common import dump, require


def register_batch(broker: Broker) -> None:
    names = (
        "job.create",
        "job.send",
        "job.cancel",
        "job.retry",
        "job.pause",
        "job.resume",
        "job.reassign",
        "job.unpin",
        "job.claim",
        "job.release",
        "batch.submit",
        "batch.validate",
        "batch.preview",
        "batch.approve",
        "batch.cancel",
        "batch.pause",
        "batch.resume",
        "batch.reassign",
        "batch.delete",
        "followup.declare",
        "followup.remove",
        "followup.retire",
        "followup.plan_due",
        "followup.cancel",
        "suppression.add",
        "suppression.remove",
        "suppression.clear",
        "quota.reserve",
        "quota.release",
        "quota.set",
        "policy.set",
        "policy.clear",
        "hold.set",
        "hold.clear",
        "dispatch.pause",
        "dispatch.resume",
    )
    broker.register(names, batch)


def batch(inv: Invocation, params: dict[str, Any]) -> Any:
    name = inv.capability
    services = inv.services
    if name == "job.create":
        return dump(
            services.outbound.create(
                account_id=require(inv, "account"),
                recipient=require(inv, "to"),
                recipient_name=inv.param("to_name"),
                subject=require(inv, "subject"),
                text=str(inv.param("text", "")),
                html=inv.param("html"),
                batch_id=str(inv.param("batch", "manual")),
            )
        )
    if name == "job.send":
        return dump(inv.broker.run(services.outbound.send(require(inv, "job"))))
    if name == "job.cancel":
        return dump(services.portability.cancel_job(require(inv, "job")))
    if name == "job.retry":
        return dump(services.failures.retry(require(inv, "job")))
    if name == "job.pause":
        return dump(services.holds.pause_job(require(inv, "job"), inv.param("reason")))
    if name == "job.resume":
        return dump(services.holds.resume_job(require(inv, "job"), inv.param("reason")))
    if name == "job.reassign":
        return dump(services.jobs.reassign([require(inv, "job")], require(inv, "to")))
    if name == "job.unpin":
        return dump(services.jobs.unpin([require(inv, "job")]))
    if name == "batch.submit":
        return dump(services.batches.submit(require(inv, "path"), inv.param("key")))
    if name == "batch.validate":
        return dump(services.batches.preview(require(inv, "path")))
    if name == "batch.preview":
        return dump(services.batches.preview(require(inv, "path")))
    if name == "batch.approve":
        return dump(
            inv.broker.run(
                services.batches.approve(
                    require(inv, "batch"), str(inv.param("mode", "all"))
                )
            )
        )
    if name == "batch.cancel":
        return dump(services.batches.cancel(require(inv, "batch")))
    if name == "batch.pause":
        return dump(
            services.holds.pause_batch(require(inv, "batch"), inv.param("reason"))
        )
    if name == "batch.resume":
        return dump(
            services.holds.resume_batch(require(inv, "batch"), inv.param("reason"))
        )
    if name == "batch.delete":
        return dump(
            services.portability.delete_batch(require(inv, "batch"), dry_run=False)
        )
    if name.startswith("followup."):
        return followup_action(inv, params)
    if name.startswith("policy."):
        return policy_action(inv, params)
    if name in {"hold.set", "hold.clear"}:
        return hold_action(inv)
    if name in {"dispatch.pause", "dispatch.resume"}:
        target = (
            services.holds.pause_service
            if name.endswith("pause")
            else services.holds.resume_service
        )
        return dump(target(inv.param("reason")))
    if name.startswith("quota."):
        return {"ok": True, "capability": name}
    return {"ok": True, "capability": name, "batch": inv.param("batch")}


def followup_action(inv: Invocation, params: dict[str, Any]) -> Any:
    services = inv.services
    name = inv.capability
    if name == "followup.plan_due":
        services.followups.plan_due()
        return {"ok": True}
    if name == "followup.cancel":
        services.followups.cancel_stopped()
        return {"ok": True}
    if name == "followup.declare":
        return dump(
            services.followups.declare(
                require(inv, "batch"),
                require(inv, "step"),
                path=require(inv, "path"),
                kind=inv.param("kind"),
                version=inv.param("version"),
                dry_run=bool(inv.param("dry_run", False)),
            )
        )
    if name == "followup.remove":
        return dump(
            services.followups.remove(require(inv, "batch"), require(inv, "step"))
        )
    return dump(services.followups.retire(require(inv, "batch"), require(inv, "step")))


def policy_action(inv: Invocation, params: dict[str, Any]) -> Any:
    services = inv.services
    target = inv.param("account")
    values = dict(params.get("values") or {})
    if inv.capability.endswith("clear"):
        if target:
            return dump(services.policy_overrides.clear_account(str(target)))
        return dump(services.policy_overrides.clear_global())
    if target:
        return dump(services.policy_overrides.set_account(str(target), values))
    return dump(services.policy_overrides.set_global(values))


def hold_action(inv: Invocation) -> Any:
    services = inv.services
    reason = inv.param("reason")
    target = inv.param("target")
    if target == "service":
        fn = (
            services.holds.pause_service
            if inv.capability == "hold.set"
            else services.holds.resume_service
        )
        return dump(fn(reason))
    if target == "account":
        fn = (
            services.holds.pause_account
            if inv.capability == "hold.set"
            else services.holds.resume_account
        )
        return dump(fn(require(inv, "account"), reason))
    if target == "batch":
        fn = (
            services.holds.pause_batch
            if inv.capability == "hold.set"
            else services.holds.resume_batch
        )
        return dump(fn(require(inv, "batch"), reason))
    fn = (
        services.holds.pause_job
        if inv.capability == "hold.set"
        else services.holds.resume_job
    )
    return dump(fn(require(inv, "job"), reason))
