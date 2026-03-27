from dataclasses import dataclass
from typing import Any

import pulumi_aws as aws


@dataclass(frozen=True)
class StorageResources:
    raw_video_bucket: aws.s3.BucketV2
    evidence_bucket: aws.s3.BucketV2
    reports_bucket: aws.s3.BucketV2


def _create_lifecycle_rule(
    lifecycle: dict[str, Any], enable_versioning: bool
) -> aws.s3.BucketLifecycleConfigurationV2RuleArgs:
    transitions_cfg = lifecycle.get("transitions", [])
    transitions = [
        aws.s3.BucketLifecycleConfigurationV2RuleTransitionArgs(
            days=int(item["days"]),
            storage_class=str(item["storageClass"]),
        )
        for item in transitions_cfg
        if "days" in item and "storageClass" in item
    ]

    noncurrent_transitions = []
    if enable_versioning:
        noncurrent_transitions_cfg = lifecycle.get("noncurrentTransitions", [])
        noncurrent_transitions = [
            aws.s3.BucketLifecycleConfigurationV2RuleNoncurrentVersionTransitionArgs(
                noncurrent_days=int(item["days"]),
                storage_class=str(item["storageClass"]),
            )
            for item in noncurrent_transitions_cfg
            if "days" in item and "storageClass" in item
        ]

    expiration = None
    if "expireDays" in lifecycle:
        expiration = aws.s3.BucketLifecycleConfigurationV2RuleExpirationArgs(
            days=int(lifecycle["expireDays"])
        )
    elif lifecycle.get("cleanDeleteMarkers"):
        expiration = aws.s3.BucketLifecycleConfigurationV2RuleExpirationArgs(
            expired_object_delete_marker=True
        )

    noncurrent_expiration = None
    if enable_versioning and "noncurrentExpireDays" in lifecycle:
        noncurrent_expiration = aws.s3.BucketLifecycleConfigurationV2RuleNoncurrentVersionExpirationArgs(
            noncurrent_days=int(lifecycle["noncurrentExpireDays"])
        )

    abort_incomplete = None
    if "abortMultipartDays" in lifecycle:
        abort_incomplete = aws.s3.BucketLifecycleConfigurationV2RuleAbortIncompleteMultipartUploadArgs(
            days_after_initiation=int(lifecycle["abortMultipartDays"])
        )

    return aws.s3.BucketLifecycleConfigurationV2RuleArgs(
        id="default-lifecycle",
        status="Enabled",
        filter=aws.s3.BucketLifecycleConfigurationV2RuleFilterArgs(),
        transitions=transitions or None,
        noncurrent_version_transitions=noncurrent_transitions or None,
        expiration=expiration,
        noncurrent_version_expiration=noncurrent_expiration,
        abort_incomplete_multipart_upload=abort_incomplete,
    )


def create_secure_bucket(
    name: str,
    prefix: str,
    enable_versioning: bool = True,
    lifecycle: dict[str, Any] | None = None,
    tags: dict[str, str] | None = None,
) -> aws.s3.BucketV2:
    resolved_tags = dict(tags or {})
    resolved_tags.setdefault("Name", f"{prefix}-{name}")

    bucket = aws.s3.BucketV2(
        name,
        bucket_prefix=f"{prefix}-{name}-",
        force_destroy=False,
        tags=resolved_tags,
    )

    aws.s3.BucketPublicAccessBlock(
        f"{name}-public-access",
        bucket=bucket.id,
        block_public_acls=True,
        block_public_policy=True,
        ignore_public_acls=True,
        restrict_public_buckets=True,
    )

    aws.s3.BucketServerSideEncryptionConfigurationV2(
        f"{name}-encryption",
        bucket=bucket.id,
        rules=[
            aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
                apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
                    sse_algorithm="AES256"
                )
            )
        ],
    )

    aws.s3.BucketVersioningV2(
        f"{name}-versioning",
        bucket=bucket.id,
        versioning_configuration=aws.s3.BucketVersioningV2VersioningConfigurationArgs(
            status="Enabled" if enable_versioning else "Suspended"
        ),
    )

    if lifecycle:
        aws.s3.BucketLifecycleConfigurationV2(
            f"{name}-lifecycle",
            bucket=bucket.id,
            rules=[_create_lifecycle_rule(lifecycle, enable_versioning)],
        )

    return bucket

