"""S3 → SQS + metadata Lambda — names, runtime, and code path live in this stack."""

import pulumi
import pulumi_aws as aws

from pulumi_aws_modules.database import DatabaseResources
from pulumi_aws_modules.events import (
    EventResources,
    MetadataIngestFanoutConfig,
    MetadataWriterLambdaConfig,
    create_events,
)
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


def create_metadata_events(
    prefix: str,
    storage: dict[str, aws.s3.BucketV2],
    messaging: dict[str, dict[str, aws.sqs.Queue]],
    database: DatabaseResources,
) -> EventResources:
    fanout = MetadataIngestFanoutConfig(
        ingest_queue_policy_pulumi_name=f"{prefix}-ingest-queue-raw-bucket-policy",
        source_bucket_to_queue_policy_sid="AllowRawBucketToSendIngest",
        lambda_invoke_permission_logical_name=f"{prefix}-raw-bucket-invoke-metadata-lambda",
        bucket_notification_logical_name=f"{prefix}-raw-bucket-events",
    )
    lambda_cfg = MetadataWriterLambdaConfig(
        lambda_role_logical_name=f"{prefix}-metadata-lambda-role",
        iam_role_name=f"{prefix}-metadata-lambda-role",
        basic_execution_attachment_logical_name=f"{prefix}-metadata-lambda-basic-exec",
        inline_policy_logical_name=f"{prefix}-metadata-lambda-inline-policy",
        function_logical_name=f"{prefix}-metadata-writer",
        function_name=f"{prefix}-metadata-writer",
        runtime="python3.11",
        handler="metadata_handler.handler",
        code=pulumi.AssetArchive(
            {
                ".": pulumi.FileArchive("./lambda_handlers/metadata_writer"),
            }
        ),
        timeout_seconds=30,
        environment={"TABLE_NAME": database.ingest_metadata_table.name},
    )
    return create_events(
        _as_storage_resources(storage),
        _as_messaging_resources(messaging),
        database,
        fanout=fanout,
        metadata_lambda=lambda_cfg,
    )


def export_events_outputs(events: EventResources) -> None:
    pulumi.export("metadataWriterLambdaName", events.metadata_lambda.name)
