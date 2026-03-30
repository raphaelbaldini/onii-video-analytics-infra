from dataclasses import dataclass

import pulumi
import pulumi_aws as aws

from modules.compute import ComputeResources, create_compute
from modules.iam import IdentityResources
from modules.network import NetworkResources
from modules.scaling import create_queue_depth_scaling


@dataclass(frozen=True)
class ComputeResourceSet:
    ingest: ComputeResources
    stage2: ComputeResources


def create_compute_resources(
    prefix: str,
    network: NetworkResources,
    messaging: dict[str, dict[str, aws.sqs.Queue]],
    identity: IdentityResources,
    min_size: int,
    max_size: int,
    instance_types: list[str],
    worker_ami_id: str | None = None,
    worker_ami_ssm_parameter: str | None = None,
    spot_max_price: str | None = None,
    scale_out_start_queue_depth: int = 10,
    queue_depth_step: int = 10,
    tags: dict[str, str] | None = None,
) -> ComputeResourceSet:
    ingest_compute = create_compute(
        resource_name="video-worker",
        prefix=prefix,
        network=network,
        instance_profile_name=identity.worker_instance_profile.name,
        min_size=min_size,
        max_size=max_size,
        instance_types=instance_types,
        worker_ami_id=worker_ami_id,
        worker_ami_ssm_parameter=worker_ami_ssm_parameter,
        spot_max_price=spot_max_price,
        tags=tags,
    )

    create_queue_depth_scaling(
        prefix=prefix,
        resource_name="video-worker",
        asg=ingest_compute.worker_asg,
        queue_name=messaging["ingest"]["queue"].name,
        max_size=max_size,
        scale_out_start_queue_depth=scale_out_start_queue_depth,
        queue_depth_step=queue_depth_step,
    )

    stage2_compute = create_compute(
        resource_name="stage2-worker",
        prefix=prefix,
        network=network,
        instance_profile_name=identity.worker_instance_profile.name,
        min_size=min_size,
        max_size=max_size,
        instance_types=instance_types,
        worker_ami_id=worker_ami_id,
        worker_ami_ssm_parameter=worker_ami_ssm_parameter,
        spot_max_price=spot_max_price,
        tags=tags,
    )

    create_queue_depth_scaling(
        prefix=prefix,
        resource_name="stage2-worker",
        asg=stage2_compute.worker_asg,
        queue_name=messaging["stage2"]["queue"].name,
        max_size=max_size,
        scale_out_start_queue_depth=scale_out_start_queue_depth,
        queue_depth_step=queue_depth_step,
    )

    return ComputeResourceSet(ingest=ingest_compute, stage2=stage2_compute)


def export_compute_outputs(compute: ComputeResourceSet) -> None:
    pulumi.export("workerAsgName", compute.ingest.worker_asg.name)
    pulumi.export("stage2WorkerAsgName", compute.stage2.worker_asg.name)

