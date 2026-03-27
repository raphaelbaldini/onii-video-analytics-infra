from dataclasses import dataclass
from typing import Optional

import pulumi_aws as aws


@dataclass(frozen=True)
class DatabaseResources:
    ingest_metadata_table: aws.dynamodb.Table
    detection_results_table: aws.dynamodb.Table


def create_on_demand_table(
    resource_name: str,
    table_name: str,
    hash_key: str,
    range_key: Optional[str],
    attributes: list[aws.dynamodb.TableAttributeArgs],
    ttl_attribute_name: Optional[str] = None,
    tags: dict[str, str] | None = None,
) -> aws.dynamodb.Table:
    resolved_tags = dict(tags or {})
    resolved_tags.setdefault("Name", table_name)

    return aws.dynamodb.Table(
        resource_name,
        name=table_name,
        billing_mode="PAY_PER_REQUEST",
        hash_key=hash_key,
        range_key=range_key,
        attributes=attributes,
        ttl=aws.dynamodb.TableTtlArgs(attribute_name=ttl_attribute_name, enabled=True)
        if ttl_attribute_name
        else None,
        tags=resolved_tags,
    )

