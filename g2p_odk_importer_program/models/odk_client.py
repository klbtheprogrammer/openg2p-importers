import logging

_logger = logging.getLogger(__name__)


class ODKClient:
    def import_delta_records(
        self,
        last_sync_timestamp=None,
        skip=0,
        top=100,
    ):
        res = super().import_delta_records(last_sync_timestamp, skip, top)
        # TODO: Handle reg_info records
        return res
