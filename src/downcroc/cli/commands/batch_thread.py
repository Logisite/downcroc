from __future__ import annotations

from downcroc.cli import reltime
from downcroc.cli.output import record
from downcroc.cli.ui import card
from downcroc.cli.ui.frame import columns
from downcroc.cli.ui.session import Ui


def show(payload: dict, ui: Ui) -> None:
    batch = payload.get("batch") or {}
    counts = batch.get("counts") or {}
    record(
        {
            "batch": f"{batch.get('id')}  {batch.get('name')}",
            "state": batch.get("state"),
            "sent": counts.get("sent", 0),
            "replies": counts.get("replies", 0),
            "created": reltime.ago(batch.get("created_at")),
        }
    )
    steps = payload.get("steps") or []
    if steps:
        print()
        print(ui.bold("follow-ups"))
        for index, step in enumerate(steps):
            last = index == len(steps) - 1 and not payload.get("recipient")
            _step_line(step, last, ui)
    threads = payload.get("threads") or []
    total = int(payload.get("thread_total") or len(threads))
    if threads or total:
        print()
        title = "replies" if payload.get("recipient") else "threads"
        label = f"{title} ({total})" if total else title
        print(ui.bold(label))
        for index, thread in enumerate(threads):
            _thread_line(thread, index == len(threads) - 1, ui)
        if (
            not payload.get("recipient")
            and not payload.get("all")
            and total > len(threads)
        ):
            print(ui.dim(f"  {total - len(threads)} more, use --all"))
    recipient = payload.get("recipient")
    if recipient:
        print()
        _recipient(recipient, ui)
    elif not threads and not steps:
        print(ui.dim("no follow-ups or replies yet"))


def _step_line(step: dict, last: bool, ui: Ui) -> None:
    branch = "└─" if last else "├─"
    rule = f"{step.get('when')} +{step.get('after_days')}d"
    parts = [str(step.get("step")), rule, str(step.get("state"))]
    due = _step_due(step)
    if due:
        parts.append(due)
    if step.get("child_batch_id"):
        parts.append(f"child {step['child_batch_id']}")
    counts = _step_counts(step)
    if counts:
        parts.append(counts)
    print(f"{branch} " + "  ·  ".join(parts))


def _step_due(step: dict) -> str:
    state = step.get("state")
    if (
        state in {"awaiting_approval", "sending", "pending"}
        and step.get("next_due_at") is None
    ):
        return "due now"
    due_at = step.get("next_due_at")
    if state in {"awaiting_approval", "sending", "pending"}:
        return "due now"
    if due_at:
        return reltime.in_time(due_at)
    return ""


def _step_counts(step: dict) -> str:
    counts = step.get("counts") or {}
    items = []
    for key, label in (
        ("sent", "sent"),
        ("replied", "replied"),
        ("candidates", "due"),
        ("not_due", "waiting"),
        ("awaiting", "awaiting"),
        ("failed", "failed"),
        ("bounced", "bounced"),
        ("pending", "pending"),
    ):
        value = int(counts.get(key) or 0)
        if value:
            items.append(f"{value} {label}")
    return " ".join(items[:4])


def _thread_line(thread: dict, last: bool, ui: Ui) -> None:
    branch = "└─" if last else "├─"
    flags = []
    if thread.get("has_confirmed"):
        flags.append("confirmed")
    elif thread.get("has_probable"):
        flags.append("probable")
    if thread.get("has_bounce"):
        flags.append("bounced")
    if not flags and thread.get("reply_count"):
        flags.append(f"{thread['reply_count']} replies")
    status = ", ".join(flags) if flags else "no reply"
    seen = reltime.ago(thread.get("last_seen"))
    subject = thread.get("subject") or "(no subject)"
    print(f"{branch} {subject}  ·  {status}  ·  {seen}")
    print(f"{'   ' if last else '│  '}thread {thread.get('id')}")


def _recipient(data: dict, ui: Ui) -> None:
    print(ui.bold(f"recipient {data.get('recipient')}"))
    jobs = data.get("jobs") or []
    thread = data.get("thread") or {}
    inbound = [
        item
        for item in (thread.get("messages") or [])
        if item.get("job_id") is None or item.get("reply_state") not in {None, "none"}
    ]
    for index, job in enumerate(jobs):
        last = index == len(jobs) - 1 and not inbound
        branch = "└─" if last else "├─"
        label = "send" if not job.get("step_key") else str(job.get("step_key"))
        when = reltime.ago(job.get("sent_at") or job.get("created_at"))
        state = job.get("state")
        subject = job.get("subject") or ""
        print(f"{branch} {label}  ·  {state}  ·  {when}  ·  {subject}")
        if job.get("message_id"):
            prefix = "   " if last else "│  "
            print(f"{prefix}msg {job['message_id']}")
    if inbound:
        print()
        print(ui.bold("replies"))
        width = max(1, columns(ui) - 1)
        for index, message in enumerate(inbound):
            if index:
                print()
            payload = {**message, "reply_label": _reply_label(message)}
            for line in card.mail_card(ui, payload, width):
                print(line)
    elif thread:
        print(ui.dim("no replies in this thread"))


def _reply_label(message: dict) -> str:
    if message.get("is_dsn") or message.get("reply_state") == "bounced":
        return "bounce"
    state = message.get("reply_state") or "none"
    if state == "none":
        return "-"
    return state
