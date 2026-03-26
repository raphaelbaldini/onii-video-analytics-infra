import base64
from dataclasses import dataclass
from typing import Optional

import pulumi
import pulumi_aws as aws

from modules.database import DatabaseResources
from modules.messaging import MessagingResources
from modules.network import NetworkResources
from modules.storage import StorageResources


@dataclass(frozen=True)
class ComputeResources:
    worker_asg: aws.autoscaling.Group


def _build_worker_role(
    prefix: str,
    storage: StorageResources,
    messaging: MessagingResources,
    database: DatabaseResources,
) -> aws.iam.Role:
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
                            args[3],
                            f"{args[3]}/*",
                            args[4],
                            f"{args[4]}/*",
                            args[5],
                            f"{args[5]}/*",
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

    return role


def _latest_ami() -> str:
    ami = aws.ec2.get_ami(
        most_recent=True,
        owners=["amazon"],
        filters=[
            {"name": "name", "values": ["amzn2-ami-hvm-*-x86_64-gp2"]},
            {"name": "virtualization-type", "values": ["hvm"]},
        ],
    )
    return ami.id


def _resolve_ami_id(ami_id: Optional[str], ami_ssm_parameter: Optional[str]) -> pulumi.Input[str]:
    if ami_id:
        return ami_id
    if ami_ssm_parameter:
        return aws.ssm.get_parameter_output(name=ami_ssm_parameter).value
    return _latest_ami()


def _user_data(prefix: str) -> str:
    script = f"""#!/bin/bash
set -euo pipefail
echo "Bootstrapping unified video worker node"
yum update -y
yum install -y python3 jq awscli
cat >/opt/video-worker-role.txt <<'EOF'
unified-stage-worker
EOF
# Placeholder for pulling and launching your analysis application.
# Example:
# aws s3 cp s3://{prefix}-artifacts/video-worker/latest/worker.tar.gz /tmp/worker.tar.gz
# tar -xzf /tmp/worker.tar.gz -C /opt/video-worker
# systemctl enable --now video-worker
"""
    return base64.b64encode(script.encode("utf-8")).decode("utf-8")


def _create_asg(
    prefix: str,
    instance_profile: aws.iam.InstanceProfile,
    network: NetworkResources,
    instance_type: str,
    min_size: int,
    max_size: int,
    ami_image_id: pulumi.Input[str],
    user_data_b64: str,
) -> aws.autoscaling.Group:
    launch_template = aws.ec2.LaunchTemplate(
        "video-worker-launch-template",
        name_prefix=f"{prefix}-worker-",
        image_id=ami_image_id,
        instance_type=instance_type,
        user_data=user_data_b64,
        iam_instance_profile=aws.ec2.LaunchTemplateIamInstanceProfileArgs(
            name=instance_profile.name
        ),
        instance_market_options=aws.ec2.LaunchTemplateInstanceMarketOptionsArgs(
            market_type="spot",
            spot_options=aws.ec2.LaunchTemplateInstanceMarketOptionsSpotOptionsArgs(
                instance_interruption_behavior="terminate"
            ),
        ),
        vpc_security_group_ids=[network.worker_security_group_id],
        tag_specifications=[
            aws.ec2.LaunchTemplateTagSpecificationArgs(
                resource_type="instance",
                tags={"Name": f"{prefix}-worker"},
            )
        ],
    )

    asg = aws.autoscaling.Group(
        "video-worker-asg",
        name=f"{prefix}-video-worker-asg",
        max_size=max_size,
        min_size=min_size,
        desired_capacity=min_size,
        vpc_zone_identifiers=network.subnet_ids,
        launch_template=aws.autoscaling.GroupLaunchTemplateArgs(
            id=launch_template.id,
            version="$Latest",
        ),
        health_check_type="EC2",
        protect_from_scale_in=False,
        tags=[
            aws.autoscaling.GroupTagArgs(
                key="Name",
                value=f"{prefix}-video-worker-asg",
                propagate_at_launch=True,
            )
        ],
    )
    return asg


def _create_scaling_from_queues(
    prefix: str,
    asg: aws.autoscaling.Group,
    ingest_queue_name: pulumi.Input[str],
    stage2_queue_name: pulumi.Input[str],
) -> None:
    scale_up_policy = aws.autoscaling.Policy(
        "video-worker-scale-up",
        name=f"{prefix}-video-worker-scale-up",
        autoscaling_group_name=asg.name,
        adjustment_type="ChangeInCapacity",
        scaling_adjustment=1,
        cooldown=120,
    )

    scale_down_policy = aws.autoscaling.Policy(
        "video-worker-scale-down",
        name=f"{prefix}-video-worker-scale-down",
        autoscaling_group_name=asg.name,
        adjustment_type="ChangeInCapacity",
        scaling_adjustment=-1,
        cooldown=300,
    )

    queue_depth_queries = [
        aws.cloudwatch.MetricAlarmMetricQueryArgs(
            id="ingestDepth",
            return_data=False,
            metric=aws.cloudwatch.MetricAlarmMetricQueryMetricArgs(
                metric_name="ApproximateNumberOfMessagesVisible",
                namespace="AWS/SQS",
                period=60,
                stat="Average",
                dimensions={"QueueName": ingest_queue_name},
            ),
        ),
        aws.cloudwatch.MetricAlarmMetricQueryArgs(
            id="stage2Depth",
            return_data=False,
            metric=aws.cloudwatch.MetricAlarmMetricQueryMetricArgs(
                metric_name="ApproximateNumberOfMessagesVisible",
                namespace="AWS/SQS",
                period=60,
                stat="Average",
                dimensions={"QueueName": stage2_queue_name},
            ),
        ),
        aws.cloudwatch.MetricAlarmMetricQueryArgs(
            id="totalDepth",
            expression="ingestDepth+stage2Depth",
            label="TotalQueueDepth",
            return_data=True,
        ),
    ]

    aws.cloudwatch.MetricAlarm(
        "video-worker-queue-depth-high",
        alarm_name=f"{prefix}-queue-depth-high",
        comparison_operator="GreaterThanOrEqualToThreshold",
        threshold=1,
        evaluation_periods=2,
        datapoints_to_alarm=2,
        treat_missing_data="notBreaching",
        alarm_actions=[scale_up_policy.arn],
        metric_queries=queue_depth_queries,
    )

    aws.cloudwatch.MetricAlarm(
        "video-worker-queue-depth-idle",
        alarm_name=f"{prefix}-queue-depth-idle",
        comparison_operator="LessThanThreshold",
        threshold=1,
        evaluation_periods=10,
        datapoints_to_alarm=10,
        treat_missing_data="breaching",
        alarm_actions=[scale_down_policy.arn],
        metric_queries=queue_depth_queries,
    )


def create_compute(
    prefix: str,
    network: NetworkResources,
    storage: StorageResources,
    messaging: MessagingResources,
    database: DatabaseResources,
    min_size: int,
    max_size: int,
    instance_types: list[str],
    worker_ami_id: Optional[str] = None,
    worker_ami_ssm_parameter: Optional[str] = None,
) -> ComputeResources:
    worker_role = _build_worker_role(prefix, storage, messaging, database)
    instance_profile = aws.iam.InstanceProfile(
        "video-worker-instance-profile",
        name=f"{prefix}-video-worker-profile",
        role=worker_role.name,
    )

    worker_asg = _create_asg(
        prefix=prefix,
        instance_profile=instance_profile,
        network=network,
        instance_type=instance_types[0],
        min_size=min_size,
        max_size=max_size,
        ami_image_id=_resolve_ami_id(worker_ami_id, worker_ami_ssm_parameter),
        user_data_b64=_user_data(prefix),
    )

    _create_scaling_from_queues(
        prefix=prefix,
        asg=worker_asg,
        ingest_queue_name=messaging.ingest_queue.name,
        stage2_queue_name=messaging.stage2_queue.name,
    )

    return ComputeResources(worker_asg=worker_asg)
