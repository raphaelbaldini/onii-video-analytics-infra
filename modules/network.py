from dataclasses import dataclass

import pulumi
import pulumi_aws as aws


@dataclass(frozen=True)
class NetworkResources:
    vpc_id: pulumi.Output[str]
    subnet_ids: pulumi.Output[list[str]]
    worker_security_group_id: pulumi.Output[str]


def create_network(prefix: str) -> NetworkResources:
    default_vpc = aws.ec2.get_vpc(default=True)
    default_subnets = aws.ec2.get_subnets(filters=[{"name": "vpc-id", "values": [default_vpc.id]}])

    worker_security_group = aws.ec2.SecurityGroup(
        "worker-security-group",
        name=f"{prefix}-workers-sg",
        description="Security group for video processing workers",
        vpc_id=default_vpc.id,
        egress=[
            aws.ec2.SecurityGroupEgressArgs(
                protocol="-1",
                from_port=0,
                to_port=0,
                cidr_blocks=["0.0.0.0/0"],
                ipv6_cidr_blocks=["::/0"],
            )
        ],
        tags={"Name": f"{prefix}-workers-sg"},
    )

    return NetworkResources(
        vpc_id=pulumi.Output.from_input(default_vpc.id),
        subnet_ids=pulumi.Output.from_input(default_subnets.ids),
        worker_security_group_id=worker_security_group.id,
    )
