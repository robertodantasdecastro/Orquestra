from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ConnectorDescriptor:
    connector_id: str
    label: str
    category: str
    status: str
    description: str
    required_env: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ready"] = all(bool(os.getenv(name)) for name in self.required_env)
        return payload


def list_connector_descriptors() -> list[ConnectorDescriptor]:
    return [
        ConnectorDescriptor(
            connector_id="ec2",
            label="AWS EC2 Trainer",
            category="training",
            status="available",
            description="Sincroniza bundles e dispara jobs de treino remoto via SSH e artefatos versionados.",
            required_env=["EC2_IP"],
            capabilities=["artifact_sync", "remote_logs", "retry", "cancel", "adapter_publish"],
            config={"entrypoint": "scripts/sync_to_ec2.sh"},
        ),
        ConnectorDescriptor(
            connector_id="sagemaker_notebook_job",
            label="SageMaker Notebook Job",
            category="cloud_notebook",
            status="planned",
            description="Executa notebooks e scripts empacotados em jobs gerenciados da AWS.",
            required_env=["AWS_REGION"],
            capabilities=["notebook_job", "artifact_bundle", "remote_logs"],
            config={"phase": "v1_connector_stub"},
        ),
        ConnectorDescriptor(
            connector_id="kaggle_kernel",
            label="Kaggle Kernel",
            category="cloud_notebook",
            status="planned",
            description="Publica bundles curados em kernels do Kaggle para execucao sob demanda.",
            required_env=["KAGGLE_USERNAME", "KAGGLE_KEY"],
            capabilities=["notebook_job", "artifact_bundle", "dataset_publish"],
            config={"phase": "v1_connector_stub"},
        ),
        ConnectorDescriptor(
            connector_id="databricks_job",
            label="Databricks Job",
            category="cloud_notebook",
            status="planned",
            description="Submete pipelines e notebooks como jobs remotos com coleta de logs e outputs.",
            required_env=["DATABRICKS_HOST", "DATABRICKS_TOKEN"],
            capabilities=["notebook_job", "artifact_bundle", "remote_logs"],
            config={"phase": "v1_connector_stub"},
        ),
    ]
