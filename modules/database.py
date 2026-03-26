from dataclasses import dataclass

import pulumi_aws as aws


@dataclass(frozen=True)
class DatabaseResources:
    ingest_metadata_table: aws.dynamodb.Table
    detection_results_table: aws.dynamodb.Table


def create_database(prefix: str) -> DatabaseResources:
    ingest_metadata_table = aws.dynamodb.Table(
        "ingest-metadata-table",
        name=f"{prefix}-ingest-metadata",
        billing_mode="PAY_PER_REQUEST",
        hash_key="videoId",
        range_key="uploadedAt",
        attributes=[
            aws.dynamodb.TableAttributeArgs(name="videoId", type="S"),
            aws.dynamodb.TableAttributeArgs(name="uploadedAt", type="S"),
        ],
        ttl=aws.dynamodb.TableTtlArgs(attribute_name="ttl", enabled=True),
    )

    detection_results_table = aws.dynamodb.Table(
        "detection-results-table",
        name=f"{prefix}-detection-results",
        billing_mode="PAY_PER_REQUEST",
        hash_key="videoId",
        range_key="analysisStage",
        attributes=[
            aws.dynamodb.TableAttributeArgs(name="videoId", type="S"),
            aws.dynamodb.TableAttributeArgs(name="analysisStage", type="S"),
        ],
    )

    return DatabaseResources(
        ingest_metadata_table=ingest_metadata_table,
        detection_results_table=detection_results_table,
    )
