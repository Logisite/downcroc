from __future__ import annotations

TOPIC = """followups

  A follow-up is always a reply to the parent message. It never starts a
  new thread, and it uses the mailbox that actually sent the parent.

  Four mechanisms
    automatic   followups[] in the campaign, planned after submit
    immediate   downcroc batch followup PARENT payload.json --step fu1
    shared      downcroc batch followups declare PARENT patch.json --step fu1
    payload     downcroc batch followups declare PARENT custom.json --step fu1

  Shared patch
    {"after_days": 3, "when": "no_reply",
     "subject": "", "text": "Just following up.",
     "require_approval": true,
     "overrides": {"m7": {"skip": true},
                   "m12": {"subject": "Different subject"}}}

  Payload declaration
    {"followup": {"after_days": 3, "when": "no_reply"},
     "messages": [{"key": "m1", "to": {"email": "ana@example.com"},
                   "subject": "", "text": "One more thought"}]}

  Commands
    downcroc batch followups status PARENT
    downcroc batch followups declare PARENT FILE --step fu1 --dry-run
    downcroc batch followups declare PARENT FILE --step fu1
    downcroc batch followups remove PARENT --step fu1 --yes
    downcroc batch followups retire PARENT --step fu1 --yes

  Remove cancels unsent jobs before a child is sent. Retire keeps sent
  child history and stops further planning. A retired key stays taken;
  use a new key for a new step.

  Status states
    scheduled, pending, deferred, awaiting_approval, sending, partial,
    done, skipped, retired, cancelled_child, parent_not_sent, broken

  The sender is inherited. There is no --account flag; reassign the
  parent batch if a different mailbox must carry the thread.

  Related: batch, review, jobs
"""
