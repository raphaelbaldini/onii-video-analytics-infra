from dataclasses import dataclass
from typing import Optional

import pulumi


@dataclass(frozen=True)
class AppConfig:
    project_prefix: str
    aws_region: str
    customer_notification_email: str
    asg_min_size: int
    asg_max_size: int
    instance_types: list[str]
    worker_ami_id: Optional[str]
    worker_ami_ssm_parameter: Optional[str]
    spot_max_price: Optional[str]
    scale_out_start_queue_depth: int
    queue_depth_step: int
    resource_tags: dict[str, str]
    confidence_threshold: str
    model_stage1: str
    model_stage2: str
    work_dir: str
    # Optional: CodeBuild + GitHub OIDC role for worker AMI (see ci_resources.py).
    enable_ami_ci_resources: bool
    github_org: Optional[str]
    github_ami_factory_repo: str
    github_worker_repo: str
    # AWS CodeConnections ARN (formerly CodeStar Connections). YAML: codeConnectionsArn (preferred) or codestarConnectionArn.
    code_connection_arn: Optional[str]
    create_github_oidc_provider: bool
    ami_factory_branch: str


def _load_tags(cfg: pulumi.Config) -> dict[str, str]:
    tags: dict[str, str] = {}
    for key in ("projectTags", "budgetTags", "securityTags", "extraTags"):
        incoming = cfg.get_object(key) or {}
        if isinstance(incoming, dict):
            tags.update({str(k): str(v) for k, v in incoming.items()})
    return tags


def load_config() -> AppConfig:
    cfg = pulumi.Config()
    aws_cfg = pulumi.Config("aws")
    return AppConfig(
        project_prefix=cfg.get("projectPrefix") or pulumi.get_project(),
        aws_region=aws_cfg.require("region"),
        customer_notification_email=cfg.require("customerNotificationEmail"),
        asg_min_size=cfg.get_int("asgMinSize") or 0,
        asg_max_size=cfg.get_int("asgMaxSize") or 3,
        instance_types=cfg.get_object("instanceTypes") or ["g4dn.xlarge"],
        worker_ami_id=cfg.get("workerAmiId"),
        worker_ami_ssm_parameter=cfg.get("workerAmiSsmParameter"),
        spot_max_price=cfg.get("spotMaxPrice"),
        scale_out_start_queue_depth=cfg.get_int("scaleOutStartQueueDepth") or 10,
        queue_depth_step=cfg.get_int("queueDepthStep") or 10,
        resource_tags=_load_tags(cfg),
        confidence_threshold=cfg.get("confidenceThreshold") or "0.80",
        model_stage1=cfg.get("modelStage1") or "yolov8n.pt",
        model_stage2=cfg.get("modelStage2") or "yolov8m.pt",
        work_dir=cfg.get("workDir") or "/tmp/onii-worker",
        enable_ami_ci_resources=bool(cfg.get_bool("enableAmiCiResources")),
        github_org=cfg.get("githubOrg"),
        github_ami_factory_repo=cfg.get("githubAmiFactoryRepo") or "onii-video-analytics-ami-factory",
        github_worker_repo=cfg.get("githubWorkerRepo") or "onii-video-analytics-worker",
        code_connection_arn=cfg.get("codeConnectionsArn") or cfg.get("codestarConnectionArn"),
        create_github_oidc_provider=bool(cfg.get_bool("createGithubOidcProvider")),
        ami_factory_branch=cfg.get("amiFactoryBranch") or "main",
    )
