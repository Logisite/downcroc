from __future__ import annotations

import argparse

from downcroc.cli.parser.common import (
    BATCH_STATES,
    JOB_STATES,
    common,
    limit,
    non_negative,
)

KINDS = ["json", "followups", "csv", "template"]


def batch(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "batch",
        help="validate, submit, and manage campaigns",
        epilog=(
            "examples:\n"
            "  downcroc batch validate campaign.json\n"
            "  downcroc batch submit campaign.json --approve none\n"
            "  downcroc batch example --kind json"
        ),
    )
    actions = parser.add_subparsers(dest="action", required=False)

    listing = actions.add_parser("list", help="list batches")
    listing.add_argument("--state", choices=BATCH_STATES, help="batch state")
    limit(listing)
    common(listing)

    show = actions.add_parser("show", help="show a batch and its recipients")
    show.add_argument("batch_id")
    show.add_argument("--all", action="store_true", help="show every recipient")
    common(show)

    preview = actions.add_parser("preview", help="preview an input file")
    _source(preview)
    preview.add_argument("--key", help="show one message by key or row")
    preview.add_argument("--all", action="store_true", help="show every message")
    preview.add_argument(
        "--table",
        action="store_true",
        help="show the summary and table instead of message cards",
    )
    common(preview)

    submit = actions.add_parser(
        "submit",
        help="submit an input file",
        epilog=(
            "examples:\n"
            "  downcroc batch submit campaign.json\n"
            "  downcroc batch submit campaign.json --approve all\n"
            "  downcroc batch submit campaign.json --account acct_... --dry-run"
        ),
    )
    _source(submit)
    submit.add_argument(
        "--approve",
        choices=["none", "one", "all"],
        default="none",
        help="none holds for review, one sends a sample, all sends",
    )
    submit.add_argument(
        "--key",
        help="submit one message by key or row; a retry reuses the batch",
    )
    submit.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and preview without writing a batch",
    )
    common(submit)

    validate = actions.add_parser(
        "validate",
        help="validate an input file offline",
        epilog=(
            "examples:\n"
            "  downcroc batch validate campaign.json\n"
            "  downcroc batch validate rows.csv --template intro"
        ),
    )
    _source(validate)
    common(validate)

    schema = actions.add_parser("schema", help="print the input contract")
    common(schema)

    example = actions.add_parser("example", help="print or write a starter file")
    example.add_argument("--kind", choices=KINDS, default="json")
    example.add_argument("--write", metavar="DIR", help="write the files to DIR")
    common(example)

    approve = actions.add_parser("approve", help="approve a batch")
    approve.add_argument("batch_id")
    approve.add_argument(
        "--mode",
        choices=["one", "all"],
        default="all",
        help="one sends a sample, all sends the rest",
    )
    common(approve, yes=True)

    cancel = actions.add_parser("cancel", help="cancel a batch")
    cancel.add_argument("batch_id")
    common(cancel, yes=True)

    reassign = actions.add_parser("reassign", help="move a batch to another account")
    reassign.add_argument("batch_id")
    reassign.add_argument(
        "--to", dest="to_account_id", required=True, help="target account id"
    )
    reassign.add_argument(
        "--state",
        dest="states",
        action="append",
        choices=JOB_STATES,
        default=[],
        help="job state; repeat for several",
    )
    reassign.add_argument(
        "--include-failed", action="store_true", help="move failed jobs too"
    )
    reassign.add_argument(
        "--dry-run", action="store_true", help="report what would move"
    )
    common(reassign, yes=True)

    delete_batch = actions.add_parser("delete", help="delete a finished batch")
    delete_batch.add_argument("batch_id")
    delete_batch.add_argument(
        "--dry-run", action="store_true", help="report what would be deleted"
    )
    common(delete_batch, yes=True)

    followup = actions.add_parser("followup", help="create a follow-up step")
    followup.add_argument("batch_id")
    followup.add_argument("path")
    followup.add_argument("--step", required=True)
    followup.add_argument("--template")
    followup.add_argument("--account")
    followup.add_argument("--require-approval", action="store_true")
    common(followup)

    suppression = actions.add_parser("suppression", help="show suppressed recipients")
    suppression.add_argument("batch_id")
    common(suppression)


def _source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", help="campaign file or CSV")
    parser.add_argument(
        "--template",
        metavar="NAME|PATH",
        help="template name or directory for a CSV",
    )
    parser.add_argument(
        "--account",
        metavar="ID",
        help="pin every message to this account",
    )


def template(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "template",
        help="inspect and create CSV templates",
        epilog=(
            "examples:\n"
            "  downcroc template new intro\n"
            "  downcroc template list\n"
            "  downcroc template validate intro"
        ),
    )
    actions = parser.add_subparsers(dest="action", required=False)

    listing = actions.add_parser("list", help="list templates")
    common(listing)

    new = actions.add_parser("new", help="create a template skeleton")
    new.add_argument("name")
    common(new)

    show = actions.add_parser("show", help="show a template")
    show.add_argument("name")
    common(show)

    validate = actions.add_parser("validate", help="validate a template")
    validate.add_argument("name")
    common(validate)


def job(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "job",
        help="inspect and send jobs",
        epilog=(
            "examples:\n"
            "  downcroc job list --state queued\n"
            "  downcroc job show job_...\n"
            "  downcroc job send job_..."
        ),
    )
    actions = parser.add_subparsers(dest="action", required=False)

    listing = actions.add_parser("list", help="list jobs")
    listing.add_argument("--batch", help="filter by batch id")
    listing.add_argument("--account", help="filter by account id")
    listing.add_argument("--state", choices=JOB_STATES, help="job state")
    limit(listing)
    common(listing)

    show = actions.add_parser("show", help="show one job")
    show.add_argument("job_id")
    common(show)

    send = actions.add_parser("send", help="send one job now")
    send.add_argument("job_id")
    common(send, yes=True)

    cancel = actions.add_parser("cancel", help="cancel one queued job")
    cancel.add_argument("job_id")
    common(cancel)

    delete_job = actions.add_parser("delete", help="delete one job")
    delete_job.add_argument("job_id")
    delete_job.add_argument(
        "--force",
        action="store_true",
        help="delete a job that has not reached a terminal state",
    )
    delete_job.add_argument(
        "--dry-run", action="store_true", help="report what would be deleted"
    )
    common(delete_job, yes=True)

    reassign = actions.add_parser("reassign", help="move jobs between accounts")
    reassign.add_argument("--account", dest="from_account_id", help="source account id")
    reassign.add_argument(
        "--to",
        dest="to_account_id",
        help="target account id; omit when unpinning",
    )
    reassign.add_argument(
        "--job",
        dest="job_ids",
        action="append",
        default=[],
        help="job id; repeat for several",
    )
    reassign.add_argument(
        "--batch",
        dest="batch_ids",
        action="append",
        default=[],
        help="batch id; repeat for several",
    )
    reassign.add_argument(
        "--state",
        dest="states",
        action="append",
        choices=JOB_STATES,
        default=[],
        help="job state; repeat for several",
    )
    reassign.add_argument("--since", help="created on or after this timestamp")
    reassign.add_argument("--until", help="created before this timestamp")
    reassign.add_argument(
        "--include-failed", action="store_true", help="move failed jobs too"
    )
    policy = reassign.add_mutually_exclusive_group()
    policy.add_argument(
        "--pin",
        action="store_true",
        help="pin the selection to the target account",
    )
    policy.add_argument(
        "--unpin",
        action="store_true",
        help="route the selection at send time",
    )
    reassign.add_argument(
        "--dry-run", action="store_true", help="report what would move"
    )
    common(reassign, yes=True)

    attempts = actions.add_parser("attempts", help="show the send attempts for a job")
    attempts.add_argument("job_id")
    common(attempts)

    create = actions.add_parser("create", help="create a manual job")
    create.add_argument(
        "--account", required=True, dest="account_id", help="sending account id"
    )
    create.add_argument(
        "--to", required=True, dest="recipient", help="recipient address"
    )
    create.add_argument("--name", dest="recipient_name", help="recipient name")
    create.add_argument("--subject", required=True, help="subject line")
    text = create.add_mutually_exclusive_group()
    text.add_argument("--text", help="plain text body")
    text.add_argument("--text-file", help="read the text body from a file")
    html = create.add_mutually_exclusive_group()
    html.add_argument("--html", help="HTML body")
    html.add_argument("--html-file", help="read the HTML body from a file")
    create.add_argument(
        "--batch", default="manual", help="batch id to group the job under"
    )
    create.add_argument(
        "--send", action="store_true", help="send immediately after creating"
    )
    create.add_argument(
        "--force",
        action="store_true",
        help="queue even when the account is not connected",
    )
    common(create, yes=True)


def failed(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser("failed", help="inspect and retry failures")
    actions = parser.add_subparsers(dest="action", required=False)

    listing = actions.add_parser("list", help="list failed jobs")
    limit(listing)
    common(listing)

    show = actions.add_parser("show", help="show one failure")
    show.add_argument("job_id")
    common(show)

    retry = actions.add_parser("retry", help="retry one failure")
    retry.add_argument("job_id")
    common(retry)

    retry_all = actions.add_parser("retry-all", help="retry every failure")
    common(retry_all, yes=True)

    forget = actions.add_parser("forget", help="forget one failure")
    forget.add_argument("job_id")
    common(forget, yes=True)

    purge = actions.add_parser("purge", help="forget failures by state or age")
    purge.add_argument(
        "--state",
        dest="states",
        action="append",
        choices=JOB_STATES,
        default=[],
        help="job state; repeat for several",
    )
    purge.add_argument(
        "--older-than", dest="older_than", type=non_negative, help="days"
    )
    purge.add_argument(
        "--dry-run", action="store_true", help="report what would be forgotten"
    )
    common(purge, yes=True)
