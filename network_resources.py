import pulumi

from modules.network import NetworkResources, create_worker_security_group, get_default_network


def create_network(prefix: str, tags: dict[str, str] | None = None) -> NetworkResources:
    vpc_id, subnet_ids = get_default_network()
    worker_security_group = create_worker_security_group(
        prefix=prefix,
        vpc_id=vpc_id,
        tags=tags,
    )

    return NetworkResources(
        vpc_id=pulumi.Output.from_input(vpc_id),
        subnet_ids=pulumi.Output.from_input(subnet_ids),
        worker_security_group_id=worker_security_group.id,
    )


def export_network_outputs(network: NetworkResources) -> None:
    pulumi.export("workerSecurityGroupId", network.worker_security_group_id)

