from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ServiceHealth:
    status: str
    service: str
    version: str


def get_health(service: str, version: str = "0.0.0-phase09") -> ServiceHealth:
    return ServiceHealth(status="ok", service=service, version=version)
