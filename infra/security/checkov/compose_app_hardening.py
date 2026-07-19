"""Check the Compose security context required by the application containers."""

from typing import Any

from checkov.common.bridgecrew.severities import get_severity
from checkov.common.models.enums import CheckCategories, CheckResult
from checkov.yaml_doc.base_yaml_check import BaseYamlCheck
from checkov.yaml_doc.enums import BlockType


class ComposeApplicationHardening(BaseYamlCheck):
    def __init__(self) -> None:
        super().__init__(
            name="Application Compose services use least-privilege runtime settings",
            id="CKV_AEGIS_1",
            categories=(CheckCategories.GENERAL_SECURITY, CheckCategories.SUPPLY_CHAIN),
            supported_entities=("services",),
            block_type=BlockType.OBJECT,
        )
        self.guideline = "https://docs.docker.com/engine/security/"
        self.severity = get_severity("HIGH")

    def scan_entity_conf(self, conf: dict[str, Any], entity_type: str) -> CheckResult:
        required_services = ("api", "web", "worker", "simulator")
        if not isinstance(conf, dict):
            return CheckResult.FAILED

        result = CheckResult.PASSED
        for service_name in required_services:
            service = conf.get(service_name)
            if not isinstance(service, dict):
                result = CheckResult.FAILED
                continue

            self.evaluated_keys.extend(
                [
                    f"services.{service_name}.read_only",
                    f"services.{service_name}.tmpfs",
                    f"services.{service_name}.cap_drop",
                    f"services.{service_name}.security_opt",
                ]
            )
            tmpfs = service.get("tmpfs") or []
            cap_drop = service.get("cap_drop") or []
            security_opt = service.get("security_opt") or []
            if (
                service.get("read_only") is not True
                or not any(str(entry).split(":", 1)[0] == "/tmp" for entry in tmpfs)
                or "ALL" not in cap_drop
                or "no-new-privileges:true" not in security_opt
            ):
                result = CheckResult.FAILED

        return result


check = ComposeApplicationHardening()
