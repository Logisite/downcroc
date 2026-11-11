from __future__ import annotations

from dataclasses import dataclass

from downcroc.backup import BackupService, RestoreService
from downcroc.core.bootstrap.foundation import Foundation
from downcroc.core.config_service import ConfigService
from downcroc.core.connectivity import ConnectivityMonitor
from downcroc.core.followups import FollowUpService


@dataclass
class Support:
    backup: BackupService
    restore: RestoreService
    config: ConfigService
    connectivity: ConnectivityMonitor


def build_support(foundation: Foundation, followups: FollowUpService) -> Support:
    connectivity = ConnectivityMonitor(
        foundation.settings.connectivity,
        foundation.connectivity_state,
        foundation.bus,
        foundation.log,
    )
    connectivity.start()
    return Support(
        backup=BackupService(foundation.paths, foundation.log),
        restore=RestoreService(foundation.paths, foundation.log),
        config=ConfigService(
            foundation.paths,
            foundation.settings,
            foundation.log,
            followups,
        ),
        connectivity=connectivity,
    )
