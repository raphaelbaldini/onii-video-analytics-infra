"""
SSM parameters for the video worker AMI bootstrap.

We use **multiple String parameters** under ``/{prefix}/{stack}/worker/env/{KEY}`` (pass
``pulumi.get_stack()`` as ``worker_env_environment``) so the
existing bootstrap script can use ``get-parameters-by-path`` with no changes.

**Single JSON value** is also possible: one SSM parameter whose value is JSON, built with
``pulumi.Output.all(...).apply(json.dumps)``. That reduces Pulumi/SSM object count and
updates atomically, but you must change ``bootstrap_worker.sh`` to fetch that parameter,
parse JSON, and write ``/etc/video-worker/env`` (systemd ``EnvironmentFile`` expects
``KEY=value`` lines, not JSON). Multiple parameters stay simpler if you want granular
IAM or to match the current AMI factory docs unchanged.
"""

import pulumi

from pulumi_aws_modules.database import DatabaseResources
from pulumi_aws_modules.security.ssm import create_string_parameter

from messaging_resources import MessagingResourceMap


def create_worker_environment_ssm_parameters(
    prefix: str,
    messaging: MessagingResourceMap,
    database: DatabaseResources,
    *,
    worker_env_environment: str = "dev",
    tags: dict[str, str] | None = None,
    aws_region: str | None = None,
    confidence_threshold: str = "0.80",
    model_stage1: str = "yolov8n.pt",
    model_stage2: str = "yolov8m.pt",
    work_dir: str = "/tmp/onii-worker",
) -> str:
    """
    Create SSM parameters the worker AMI bake reads (path prefix matches AMI factory default).

    Returns the path prefix (for stack export), e.g. ``/onii-video/dev/worker/env``.
    """
    base = f"/{prefix}/{worker_env_environment}/worker/env"
    region = aws_region if aws_region is not None else pulumi.Config("aws").require("region")

    create_string_parameter(
        "worker-env-aws-region",
        f"{base}/AWS_REGION",
        region,
        description="Video worker: AWS_REGION",
        tags=tags,
    )
    create_string_parameter(
        "worker-env-ingest-queue-url",
        f"{base}/INGEST_QUEUE_URL",
        messaging["ingest"]["queue"].url,
        description="Video worker: ingest SQS URL",
        tags=tags,
    )
    create_string_parameter(
        "worker-env-stage2-queue-url",
        f"{base}/STAGE2_QUEUE_URL",
        messaging["stage2"]["queue"].url,
        description="Video worker: stage2 SQS URL",
        tags=tags,
    )
    create_string_parameter(
        "worker-env-results-table",
        f"{base}/RESULTS_TABLE_NAME",
        database.detection_results_table.name,
        description="Video worker: DynamoDB detection results table",
        tags=tags,
    )
    create_string_parameter(
        "worker-env-confidence",
        f"{base}/CONFIDENCE_THRESHOLD",
        confidence_threshold,
        description="Video worker: CONFIDENCE_THRESHOLD",
        tags=tags,
    )
    create_string_parameter(
        "worker-env-model-stage1",
        f"{base}/MODEL_STAGE1",
        model_stage1,
        description="Video worker: MODEL_STAGE1",
        tags=tags,
    )
    create_string_parameter(
        "worker-env-model-stage2",
        f"{base}/MODEL_STAGE2",
        model_stage2,
        description="Video worker: MODEL_STAGE2",
        tags=tags,
    )
    create_string_parameter(
        "worker-env-work-dir",
        f"{base}/WORK_DIR",
        work_dir,
        description="Video worker: WORK_DIR",
        tags=tags,
    )
    return base


def export_worker_ssm_outputs(path_prefix: str) -> None:
    pulumi.export("workerEnvSsmPathPrefix", path_prefix)
