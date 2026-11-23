from __future__ import annotations

from typing import Any

from downcroc.extensions.broker import Broker, Invocation
from downcroc.extensions.capabilities.common import dump, require


def register_accounts(broker: Broker) -> None:
    names = (
        "account.create",
        "account.connect",
        "account.disconnect",
        "account.pause",
        "account.resume",
        "account.archive",
        "account.unarchive",
        "account.reassign",
        "account.delete",
        "account.rename",
        "account.set_credentials",
    )
    broker.register(names, accounts)


def accounts(inv: Invocation, params: dict[str, Any]) -> Any:
    name = inv.capability
    services = inv.services
    if name == "account.create":
        return dump(
            services.accounts.create(
                require(inv, "provider"),
                require(inv, "address"),
                str(inv.param("label", "")),
            )
        )
    if name == "account.connect":
        return dump(services.accounts.start_attempt(require(inv, "account")))
    if name == "account.disconnect":
        return dump(services.accounts.verify(require(inv, "account"), refresh=True))
    if name == "account.pause":
        return dump(
            services.holds.pause_account(require(inv, "account"), inv.param("reason"))
        )
    if name == "account.resume":
        return dump(services.holds.resume_account(require(inv, "account")))
    if name == "account.archive":
        return dump(services.accounts.archive(require(inv, "account")))
    if name == "account.unarchive":
        return dump(services.accounts.unarchive(require(inv, "account")))
    if name == "account.reassign":
        return dump(
            services.portability.reassign(
                account_id=require(inv, "account"),
                to_account_id=inv.param("to"),
                job_ids=inv.param("job_ids") or [],
            )
        )
    if name == "account.delete":
        return dump(services.accounts.delete(require(inv, "account"), confirm=True))
    return {"ok": True, "capability": name, "account": inv.param("account")}
