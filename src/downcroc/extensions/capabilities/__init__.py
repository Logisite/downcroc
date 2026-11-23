from __future__ import annotations

from downcroc.extensions.broker import Broker


def register_capabilities(broker: Broker) -> None:
    from downcroc.extensions.capabilities.accounts import register_accounts
    from downcroc.extensions.capabilities.batch import register_batch
    from downcroc.extensions.capabilities.inspection import register_inspection
    from downcroc.extensions.capabilities.mail import register_mail
    from downcroc.extensions.capabilities.network import register_network
    from downcroc.extensions.capabilities.state import register_state
    from downcroc.extensions.capabilities.system import register_system
    from downcroc.extensions.capabilities.transport import register_transport
    from downcroc.extensions.capabilities.vault import register_vault

    for register in (
        register_state,
        register_inspection,
        register_mail,
        register_accounts,
        register_transport,
        register_batch,
        register_vault,
        register_system,
        register_network,
    ):
        register(broker)
