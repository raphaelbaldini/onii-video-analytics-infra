import pulumi
import pulumi_aws as aws

from modules.database import DatabaseResources
from modules.iam import IdentityResources, create_worker_identity
from modules.messaging import MessagingResources
from modules.storage import StorageResources


def _as_storage_resources(storage: dict[str, aws.s3.BucketV2]) -> StorageResources:
    return StorageResources(
        raw_video_bucket=storage["raw-videos"],
        evidence_bucket=storage["evidence"],
        reports_bucket=storage["reports"],
    )


def _as_messaging_resources(
    messaging: dict[str, dict[str, aws.sqs.Queue]],
) -> MessagingResources:
    return MessagingResources(
        ingest_queue=messaging["ingest"]["queue"],
        ingest_dlq=messaging["ingest"]["dlq"],
        stage2_queue=messaging["stage2"]["queue"],
        stage2_dlq=messaging["stage2"]["dlq"],
    )


def create_identity_resources(
    prefix: str,
    storage: dict[str, aws.s3.BucketV2],
    messaging: dict[str, dict[str, aws.sqs.Queue]],
    database: DatabaseResources,
    tags: dict[str, str] | None = None,
) -> IdentityResources:
    return create_worker_identity(
        prefix=prefix,
        storage=_as_storage_resources(storage),
        messaging=_as_messaging_resources(messaging),
        database=database,
        tags=tags,
    )


def export_identity_outputs(identity: IdentityResources) -> None:
    pulumi.export("workerRoleName", identity.worker_role.name)
    pulumi.export("workerInstanceProfileName", identity.worker_instance_profile.name)

