from __future__ import annotations

from typing import Any

from downcroc.extensions.broker import Broker, Invocation
from downcroc.extensions.capabilities.common import dump, require


def register_mail(broker: Broker) -> None:
    names = (
        "mail.send",
        "mail.reply",
        "mail.forward",
        "mail.fetch",
        "mail.sync",
        "mail.mark_read",
        "mail.mark_unread",
        "mail.flag",
        "mail.move",
        "mail.delete",
        "mail.prune",
        "mail.classify",
        "mail.attribute_reply",
    )
    broker.register(names, mail)


def mail(inv: Invocation, params: dict[str, Any]) -> Any:
    name = inv.capability
    if name == "mail.send":
        return send(inv, params, require(inv, "account"))
    if name in {"mail.reply", "mail.forward"}:
        return reply(inv, params, name == "mail.forward")
    if name == "mail.sync":
        inv.services.inbound.sync_now(require(inv, "account"))
        return {"ok": True}
    if name == "mail.fetch":
        return {"ok": True, "account": require(inv, "account")}
    if name == "mail.prune":
        return dump(inv.services.retention.prune())
    if name in {
        "mail.mark_read",
        "mail.mark_unread",
        "mail.flag",
        "mail.move",
        "mail.delete",
    }:
        return {"ok": True, "message": require(inv, "message")}
    return {"ok": True, "capability": name}


def send(inv: Invocation, params: dict[str, Any], account: str) -> Any:
    job = inv.services.outbound.create(
        account_id=account,
        recipient=require(inv, "to"),
        recipient_name=inv.param("to_name"),
        subject=require(inv, "subject"),
        text=str(inv.param("text", "")),
        html=inv.param("html"),
    )
    inv.services.jobs.set_extension(job.id, inv.extension)
    sent = inv.broker.run(inv.services.outbound.send(job.id))
    return {"job": sent.id, "message_id": sent.message_id}


def reply(inv: Invocation, params: dict[str, Any], forward: bool) -> Any:
    message = inv.services.messages.get_message(require(inv, "message"))
    prefix = "Fwd:" if forward else "Re:"
    subject = str(inv.param("subject") or _subject(message.subject, prefix))
    text = str(inv.param("text", ""))
    if forward:
        text = f"{text}\n\nOriginal message:\n{message.subject}"
    job = inv.services.outbound.create(
        account_id=message.account_id,
        recipient=message.from_address,
        recipient_name=message.from_name,
        subject=subject,
        text=text,
        html=None,
    )
    parent = job_id = message.job_id
    root = job_id
    if job_id:
        parent_job = inv.services.jobs.get(job_id)
        root = parent_job.thread_root_job_id or job_id
    inv.services.jobs.set_thread(job.id, parent_job_id=parent, thread_root_job_id=root)
    inv.services.jobs.set_extension(job.id, inv.extension)
    sent = inv.broker.run(inv.services.outbound.send(job.id))
    return {"job": sent.id, "message_id": sent.message_id, "in_reply_to": job_id}


def _subject(subject: str, prefix: str) -> str:
    value = subject.strip()
    while value.lower().startswith(("re:", "fwd:")):
        value = value[value.index(":") + 1 :].strip()
    return f"{prefix} {value}"
