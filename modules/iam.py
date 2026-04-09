from dataclasses import dataclass

import pulumi
import pulumi_aws as aws

from modules.database import DatabaseResources
from modules.messaging import MessagingResources
from modules.storage import StorageResources


@dataclass(frozen=True)
class IdentityResources:
    worker_role: aws.iam.Role
    worker_instance_profile: aws.iam.InstanceProfile


def create_worker_identity(
    prefix: str,
    storage: StorageResources,
    messaging: MessagingResources,
    database: DatabaseResources,
    tags: dict[str, str] | None = None,
) -> IdentityResources:
    assume_policy = aws.iam.get_policy_document(
        statements=[
            aws.iam.GetPolicyDocumentStatementArgs(
                actions=["sts:AssumeRole"],
                principals=[
                    aws.iam.GetPolicyDocumentStatementPrincipalArgs(
                        type="Service",
                        identifiers=["ec2.amazonaws.com"],
                    )
                ],
            )
        ]
    )

    role = aws.iam.Role(
        "video-worker-role",
        name=f"{prefix}-video-worker-role",
        assume_role_policy=assume_policy.json,
        tags={**(tags or {}), "Name": f"{prefix}-video-worker-role"},
    )

    policy_doc = pulumi.Output.all(
        messaging.ingest_queue.arn,
        messaging.stage2_queue.arn,
        database.detection_results_table.arn,
        database.ingest_metadata_table.arn,
        storage.raw_video_bucket.arn,
        storage.evidence_bucket.arn,
        storage.reports_bucket.arn,
    ).apply(
        lambda args: pulumi.Output.json_dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "sqs:ReceiveMessage",
                            "sqs:DeleteMessage",
                            "sqs:ChangeMessageVisibility",
                            "sqs:GetQueueAttributes",
                            "sqs:SendMessage",
                        ],
                        "Resource": [args[0], args[1]],
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:PutItem",
                            "dynamodb:UpdateItem",
                            "dynamodb:GetItem",
                            "dynamodb:Query",
                        ],
                        "Resource": [args[2], args[3]],
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
                        "Resource": [
                            args[4],
                            f"{args[4]}/*",
                            args[5],
                            f"{args[5]}/*",
                            args[6],
                            f"{args[6]}/*",
                        ],
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["ssm:GetParameter", "ssm:GetParameters"],
                        "Resource": "*",
                    },
                ],
            }
        )
    )

    aws.iam.RolePolicy(
        "video-worker-inline-policy",
        role=role.id,
        policy=policy_doc,
    )

    aws.iam.RolePolicyAttachment(
        "video-worker-ssm-managed-policy",
        role=role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
    )

    instance_profile = aws.iam.InstanceProfile(
        "video-worker-instance-profile",
        name=f"{prefix}-video-worker-profile",
        role=role.name,
        tags={**(tags or {}), "Name": f"{prefix}-video-worker-profile"},
    )

    return IdentityResources(
        worker_role=role,
        worker_instance_profile=instance_profile,
    )

