import pulumi
import pulumi_aws as aws

from pulumi_aws_modules.database import DatabaseResources
from pulumi_aws_modules.security.iam import IdentityResources, create_worker_identity
from pulumi_aws_modules.messaging import MessagingResources
from pulumi_aws_modules.storage import StorageResources


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
        storage=_as_storage_resources(storage),
        messaging=_as_messaging_resources(messaging),
        database=database,
        role_name=f"{prefix}-video-worker-role",
        instance_profile_name=f"{prefix}-video-worker-profile",
        pulumi_resource_prefix=f"{prefix}-video-worker-identity",
        tags=tags,
    )


def export_identity_outputs(identity: IdentityResources) -> None:
    pulumi.export("workerRoleName", identity.worker_role.name)
    pulumi.export("workerInstanceProfileName", identity.worker_instance_profile.name)
