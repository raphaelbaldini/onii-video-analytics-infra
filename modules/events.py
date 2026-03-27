import json
from dataclasses import dataclass

import pulumi
import pulumi_aws as aws

from modules.database import DatabaseResources
from modules.messaging import MessagingResources
from modules.storage import StorageResources


@dataclass(frozen=True)
class EventResources:
    metadata_lambda: aws.lambda_.Function


def _allow_s3_to_send_to_queue(
    resource_name: str, queue: aws.sqs.Queue, bucket_arn: pulumi.Input[str], sid: str
) -> None:
    policy = pulumi.Output.all(queue.arn, bucket_arn).apply(
        lambda args: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": sid,
                        "Effect": "Allow",
                        "Principal": {"Service": "s3.amazonaws.com"},
                        "Action": "sqs:SendMessage",
                        "Resource": args[0],
                        "Condition": {"ArnEquals": {"aws:SourceArn": args[1]}},
                    }
                ],
            }
        )
    )
    aws.sqs.QueuePolicy(f"{resource_name}-policy", queue_url=queue.id, policy=policy)


def create_events(
    prefix: str,
    storage: StorageResources,
    messaging: MessagingResources,
    database: DatabaseResources,
) -> EventResources:
    _allow_s3_to_send_to_queue(
        resource_name="ingest-queue",
        queue=messaging.ingest_queue,
        bucket_arn=storage.raw_video_bucket.arn,
        sid="AllowRawBucketToSendIngest",
    )

    lambda_assume_policy = aws.iam.get_policy_document(
        statements=[
            aws.iam.GetPolicyDocumentStatementArgs(
                actions=["sts:AssumeRole"],
                principals=[
                    aws.iam.GetPolicyDocumentStatementPrincipalArgs(
                        type="Service", identifiers=["lambda.amazonaws.com"]
                    )
                ],
            )
        ]
    )

    metadata_lambda_role = aws.iam.Role(
        "metadata-writer-lambda-role",
        name=f"{prefix}-metadata-lambda-role",
        assume_role_policy=lambda_assume_policy.json,
    )

    aws.iam.RolePolicyAttachment(
        "metadata-lambda-basic-exec",
        role=metadata_lambda_role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )

    metadata_policy = pulumi.Output.all(database.ingest_metadata_table.arn).apply(
        lambda args: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["dynamodb:PutItem", "dynamodb:UpdateItem"],
                        "Resource": [args[0]],
                    }
                ],
            }
        )
    )

    aws.iam.RolePolicy(
        "metadata-lambda-policy",
        role=metadata_lambda_role.id,
        policy=metadata_policy,
    )

    metadata_lambda = aws.lambda_.Function(
        "metadata-writer",
        name=f"{prefix}-metadata-writer",
        runtime="python3.11",
        role=metadata_lambda_role.arn,
        handler="metadata_handler.handler",
        timeout=30,
        code=pulumi.AssetArchive(
            {
                ".": pulumi.FileArchive("./lambda_handlers/metadata_writer"),
            }
        ),
        environment=aws.lambda_.FunctionEnvironmentArgs(
            variables={"TABLE_NAME": database.ingest_metadata_table.name}
        ),
    )

    aws.lambda_.Permission(
        "raw-bucket-invoke-metadata-lambda",
        action="lambda:InvokeFunction",
        function=metadata_lambda.name,
        principal="s3.amazonaws.com",
        source_arn=storage.raw_video_bucket.arn,
    )
    
    aws.s3.BucketNotification(
        "raw-bucket-events",
        bucket=storage.raw_video_bucket.id,
        queues=[
            aws.s3.BucketNotificationQueueArgs(
                queue_arn=messaging.ingest_queue.arn,
                events=["s3:ObjectCreated:*"],
            )
        ],
        lambda_functions=[  # <- correct
            aws.s3.BucketNotificationLambdaFunctionArgs(
                lambda_function_arn=metadata_lambda.arn,
                events=["s3:ObjectCreated:*"],
            )
        ],
    )

    return EventResources(metadata_lambda=metadata_lambda)
