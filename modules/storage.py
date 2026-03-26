from dataclasses import dataclass

import pulumi_aws as aws


@dataclass(frozen=True)
class StorageResources:
    raw_video_bucket: aws.s3.BucketV2
    evidence_bucket: aws.s3.BucketV2
    reports_bucket: aws.s3.BucketV2


def _secure_bucket(name: str, prefix: str) -> aws.s3.BucketV2:
    bucket = aws.s3.BucketV2(
        name,
        bucket_prefix=f"{prefix}-{name}-",
        force_destroy=False,
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
            status="Enabled"
        ),
    )

    return bucket


def create_storage(prefix: str) -> StorageResources:
    return StorageResources(
        raw_video_bucket=_secure_bucket("raw-videos", prefix),
        evidence_bucket=_secure_bucket("evidence", prefix),
        reports_bucket=_secure_bucket("reports", prefix),
    )
