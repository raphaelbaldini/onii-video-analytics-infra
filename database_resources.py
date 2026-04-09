import pulumi
import pulumi_aws as aws

from pulumi_aws_modules.database import DatabaseResources, create_on_demand_table


def create_database(prefix: str, tags: dict[str, str] | None = None) -> DatabaseResources:
    ingest_metadata_table = create_on_demand_table(
        resource_name="ingest-metadata-table",
        table_name=f"{prefix}-ingest-metadata",
        hash_key="videoId",
        range_key="uploadedAt",
        attributes=[
            aws.dynamodb.TableAttributeArgs(name="videoId", type="S"),
            aws.dynamodb.TableAttributeArgs(name="uploadedAt", type="S"),
        ],
        ttl_attribute_name="ttl",
        tags=tags,
    )

    detection_results_table = create_on_demand_table(
        resource_name="detection-results-table",
        table_name=f"{prefix}-detection-results",
        hash_key="videoId",
        range_key="analysisStage",
        attributes=[
            aws.dynamodb.TableAttributeArgs(name="videoId", type="S"),
            aws.dynamodb.TableAttributeArgs(name="analysisStage", type="S"),
        ],
        tags=tags,
    )

    return DatabaseResources(
        ingest_metadata_table=ingest_metadata_table,
        detection_results_table=detection_results_table,
    )


def export_database_outputs(database: DatabaseResources) -> None:
    pulumi.export("ingestMetadataTableName", database.ingest_metadata_table.name)
    pulumi.export("detectionResultsTableName", database.detection_results_table.name)
