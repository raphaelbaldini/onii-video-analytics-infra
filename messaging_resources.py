import pulumi
import pulumi_aws as aws

from modules.messaging import create_queue_with_dlq


MessagingResourceMap = dict[str, dict[str, aws.sqs.Queue]]


def _to_export_key(name: str) -> str:
    parts = name.replace("_", "-").split("-")
    return "".join(part.capitalize() for part in parts if part)


def create_messaging(
    prefix: str,
    queue_configs: dict[str, dict[str, int]] | None = None,
    tags: dict[str, str] | None = None,
) -> MessagingResourceMap:
    if queue_configs is None:
        cfg = pulumi.Config()
        queue_configs = cfg.get_object("queues") or {
            "ingest": {"visibilityTimeoutSeconds": 300, "maxReceiveCount": 5},
            "stage2": {"visibilityTimeoutSeconds": 600, "maxReceiveCount": 5},
        }

    resources: MessagingResourceMap = {}
    for queue_key, cfg in queue_configs.items():
        visibility_timeout = int(cfg.get("visibilityTimeoutSeconds", 300))
        max_receive_count = int(cfg.get("maxReceiveCount", 5))
        retention_seconds = int(cfg.get("messageRetentionSeconds", 1209600))

        queue, dlq = create_queue_with_dlq(
            resource_name=f"{queue_key}-queue",
            queue_name=f"{prefix}-{queue_key}-queue",
            visibility_timeout_seconds=visibility_timeout,
            max_receive_count=max_receive_count,
            message_retention_seconds=retention_seconds,
            tags=tags,
        )

        resources[queue_key] = {"queue": queue, "dlq": dlq}

    return resources


def export_messaging_outputs(messaging: MessagingResourceMap) -> None:
    for queue_key, data in messaging.items():
        export_key = _to_export_key(queue_key)
        pulumi.export(f"{export_key}QueueUrl", data["queue"].url)
        pulumi.export(f"{export_key}DlqUrl", data["dlq"].url)

