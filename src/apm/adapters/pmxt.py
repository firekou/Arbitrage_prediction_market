"""PMXT is intentionally not attached in B1."""


class PmxtAdapter:
    venue_id = "pmxt"

    def discover(self) -> None:
        raise NotImplementedError("B1 does not attach a PMXT sidecar or hosted client")

    def snapshot_books(self, markets: object) -> None:
        raise NotImplementedError("B1 does not attach a PMXT sidecar or hosted client")
