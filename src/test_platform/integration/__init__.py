"""Jenkins consumer integration contracts owned by Test Platform (API-390).

Test Platform is the canonical authority for the Jenkins consumer contract:
the versioned models, the closed suite/executor catalog, the plan-to-request
compilation, the normalized outcome mapping, and receipt ingestion all live
here. project-jenkins carries only a minimal versioned consumer
representation and never reinterprets these semantics.
"""

from __future__ import annotations

from test_platform.integration.catalog import (
    ContractCatalogError,
    load_consumer_contract,
)
from test_platform.integration.compile import (
    JenkinsContractError,
    compile_jenkins_execution_request,
)
from test_platform.integration.ingest import (
    ReceiptIngestError,
    ingest_jenkins_receipt_submission,
)
from test_platform.integration.outcomes import (
    OUTCOME_DESCRIPTIONS,
    OUTCOME_RESULT_MAPPING,
)

__all__ = [
    "OUTCOME_DESCRIPTIONS",
    "OUTCOME_RESULT_MAPPING",
    "ContractCatalogError",
    "JenkinsContractError",
    "ReceiptIngestError",
    "compile_jenkins_execution_request",
    "ingest_jenkins_receipt_submission",
    "load_consumer_contract",
]
