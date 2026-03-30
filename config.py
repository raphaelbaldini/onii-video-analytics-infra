from dataclasses import dataclass
from typing import Optional

import pulumi


@dataclass(frozen=True)
class AppConfig:
    project_prefix: str
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


def _load_tags(cfg: pulumi.Config) -> dict[str, str]:
    tags: dict[str, str] = {}
    for key in ("projectTags", "budgetTags", "securityTags", "extraTags"):
        incoming = cfg.get_object(key) or {}
        if isinstance(incoming, dict):
            tags.update({str(k): str(v) for k, v in incoming.items()})
    return tags


def load_config() -> AppConfig:
    cfg = pulumi.Config()
    return AppConfig(
        project_prefix=cfg.get("projectPrefix") or pulumi.get_project(),
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
    )

