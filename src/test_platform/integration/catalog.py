"""Allowlisted loader for the built-in Jenkins consumer contract catalog."""

from __future__ import annotations

from importlib.resources import files

from pydantic import ValidationError

from test_platform.contracts import JENKINS_CONTRACT_ID, JenkinsConsumerContract
from test_platform.yaml_io import YamlContractError, parse_yaml_mapping

CONTRACT_FILES: dict[str, str] = {
    JENKINS_CONTRACT_ID: "jenkins-execution-contract.yaml",
}


class ContractCatalogError(ValueError):
    """Raised when a consumer contract identity or file is not supported."""


def load_consumer_contract(contract_id: str = JENKINS_CONTRACT_ID) -> JenkinsConsumerContract:
    """Load one allowlisted V1 Jenkins consumer contract.

    Consumers outside this repository must pin a version they were qualified
    against; an unknown contract identity is never inferred or defaulted.
    """
    filename = CONTRACT_FILES.get(contract_id)
    if filename is None:
        raise ContractCatalogError(f"unsupported consumer contract: {contract_id}")

    resource = files("test_platform").joinpath("data", "contracts", "v1", filename)
    try:
        text = resource.read_text(encoding="utf-8")
        data = parse_yaml_mapping(text, source=f"contract:{contract_id}")
        contract = JenkinsConsumerContract.model_validate(data)
    except (OSError, ValidationError, YamlContractError) as exc:
        raise ContractCatalogError(
            f"invalid built-in consumer contract: {contract_id}"
        ) from exc

    if contract.contract_id != contract_id:
        raise ContractCatalogError(
            f"consumer contract file identity mismatch: expected {contract_id}, "
            f"got {contract.contract_id}"
        )
    return contract
