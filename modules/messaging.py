from dataclasses import dataclass

import pulumi
import pulumi_aws as aws


@dataclass(frozen=True)
class MessagingResources:
    ingest_queue: aws.sqs.Queue
    ingest_dlq: aws.sqs.Queue
    stage2_queue: aws.sqs.Queue
    stage2_dlq: aws.sqs.Queue


def create_messaging(prefix: str) -> MessagingResources:
    ingest_dlq = aws.sqs.Queue(
        "ingest-dlq",
        name=f"{prefix}-ingest-dlq",
        message_retention_seconds=1209600,
    )

    ingest_queue = aws.sqs.Queue(
        "ingest-queue",
        name=f"{prefix}-ingest-queue",
        visibility_timeout_seconds=300,
        redrive_policy=ingest_dlq.arn.apply(
            lambda arn: pulumi.Output.json_dumps(
                {"deadLetterTargetArn": arn, "maxReceiveCount": 5}
            )
        ),
    )

    stage2_dlq = aws.sqs.Queue(
        "stage2-dlq",
        name=f"{prefix}-stage2-dlq",
        message_retention_seconds=1209600,
    )

    stage2_queue = aws.sqs.Queue(
        "stage2-queue",
        name=f"{prefix}-stage2-queue",
        visibility_timeout_seconds=600,
        redrive_policy=stage2_dlq.arn.apply(
            lambda arn: pulumi.Output.json_dumps(
                {"deadLetterTargetArn": arn, "maxReceiveCount": 5}
            )
        ),
    )

    return MessagingResources(
        ingest_queue=ingest_queue,
        ingest_dlq=ingest_dlq,
        stage2_queue=stage2_queue,
        stage2_dlq=stage2_dlq,
    )
