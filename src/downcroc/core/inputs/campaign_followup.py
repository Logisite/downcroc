from __future__ import annotations

from downcroc.core.inputs.field_input import (
    MAX_KEY,
    MAX_STEP_DAYS,
    MAX_SUBJECT,
    check_keys,
    is_int,
    mapping,
    optional_text,
    require_text,
)
from downcroc.core.inputs.limits import IntakeLimits
from downcroc.core.inputs.report import Issues
from downcroc.domain.campaign import FOLLOWUP_WHEN, FollowUpStep


def parse_followups(
    raw: list[object], limits: IntakeLimits, issues: Issues
) -> list[FollowUpStep]:
    steps: list[FollowUpStep] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        where = f"followups[{index}]"
        body = mapping(item, where, issues)
        check_keys(
            body,
            {
                "key",
                "after_days",
                "when",
                "subject",
                "text",
                "html",
                "require_approval",
            },
            where,
            issues,
        )
        key = require_text(body.get("key"), f"{where}.key", issues, limit=MAX_KEY)
        if key in seen:
            issues.add(
                "duplicate_step", f"step {key} is declared twice", f"{where}.key"
            )
        seen.add(key)
        after_days = body.get("after_days")
        if not is_int(after_days) or not 1 <= after_days <= MAX_STEP_DAYS:
            issues.add(
                "invalid_field",
                f"after_days must be between 1 and {MAX_STEP_DAYS}",
                f"{where}.after_days",
            )
            after_days = 1
        when = body.get("when", "no_reply")
        if when not in FOLLOWUP_WHEN:
            issues.add(
                "invalid_field",
                f"when must be one of {sorted(FOLLOWUP_WHEN)}",
                f"{where}.when",
            )
            when = "no_reply"
        subject = optional_text(
            body.get("subject"), f"{where}.subject", issues, limit=MAX_SUBJECT
        )
        text = optional_text(
            body.get("text"), f"{where}.text", issues, limit=limits.max_body_bytes
        )
        html = optional_text(
            body.get("html"), f"{where}.html", issues, limit=limits.max_body_bytes
        )
        if not text and not html:
            issues.add(
                "missing_content",
                "a follow-up step needs text or html",
                f"{where}.text",
            )
        require_approval = body.get("require_approval", False)
        if not isinstance(require_approval, bool):
            issues.add(
                "invalid_field",
                "require_approval must be a boolean",
                f"{where}.require_approval",
            )
            require_approval = False
        steps.append(
            FollowUpStep(
                key=key,
                after_days=after_days,
                when=str(when),
                subject=subject,
                text=text or "",
                html=html,
                require_approval=require_approval,
            )
        )
    return steps
