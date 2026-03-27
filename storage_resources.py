import pulumi
import pulumi_aws as aws

from modules.storage import create_secure_bucket


def _to_export_key(name: str) -> str:
    parts = name.replace("_", "-").split("-")
    return "".join(part.capitalize() for part in parts if part)


def _is_versioning_enabled(name: str, bucket_cfg: dict[str, dict]) -> bool:
    cfg = bucket_cfg.get(name, {})
    return bool(cfg.get("enableVersioning", True))


def _bucket_lifecycle(name: str, bucket_cfg: dict[str, dict]) -> dict | None:
    cfg = bucket_cfg.get(name, {})
    lifecycle = cfg.get("lifecycle")
    return lifecycle if isinstance(lifecycle, dict) else None


def create_storage(
    prefix: str,
    bucket_names: list[str] | None = None,
    tags: dict[str, str] | None = None,
) -> dict[str, aws.s3.BucketV2]:
    cfg = pulumi.Config()

    if bucket_names is None:
        bucket_names = cfg.get_object("buckets") or ["raw-videos", "evidence", "reports"]
    bucket_cfg = cfg.get_object("bucketsConfig") or {}

    buckets: dict[str, aws.s3.BucketV2] = {}
    for name in bucket_names:
        buckets[name] = create_secure_bucket(
            name=name,
            prefix=prefix,
            enable_versioning=_is_versioning_enabled(name, bucket_cfg),
            lifecycle=_bucket_lifecycle(name, bucket_cfg),
            tags=tags,
        )
    return buckets


def export_storage_outputs(storage: dict[str, aws.s3.BucketV2]) -> None:
    for name, bucket in storage.items():
        export_key = _to_export_key(name)
        pulumi.export(f"{export_key}BucketName", bucket.bucket)
