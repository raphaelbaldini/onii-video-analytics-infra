from dataclasses import dataclass

import pulumi
import pulumi_aws as aws


@dataclass(frozen=True)
class MessagingResources:
    ingest_queue: aws.sqs.Queue
    ingest_dlq: aws.sqs.Queue
    stage2_queue: aws.sqs.Queue
    stage2_dlq: aws.sqs.Queue


def create_queue_with_dlq(
    resource_name: str,
    queue_name: str,
    visibility_timeout_seconds: int,
    max_receive_count: int = 5,
    message_retention_seconds: int = 1209600,
    tags: dict[str, str] | None = None,
) -> tuple[aws.sqs.Queue, aws.sqs.Queue]:
    resolved_tags = dict(tags or {})

    dlq = aws.sqs.Queue(
        f"{resource_name}-dlq",
        name=f"{queue_name}-dlq",
        message_retention_seconds=message_retention_seconds,
        tags={**resolved_tags, "Name": f"{queue_name}-dlq"},
    )

    queue = aws.sqs.Queue(
        resource_name,
        name=queue_name,
        visibility_timeout_seconds=visibility_timeout_seconds,
        tags={**resolved_tags, "Name": queue_name},
        redrive_policy=dlq.arn.apply(
            lambda arn: pulumi.Output.json_dumps(
                {"deadLetterTargetArn": arn, "maxReceiveCount": max_receive_count}
            )
        ),
    )

    return queue, dlq

