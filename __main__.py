import pulumi

from config import load_config
from compute_resources import create_compute_resources, export_compute_outputs
from database_resources import create_database, export_database_outputs
from iam_resources import create_identity_resources, export_identity_outputs
from network_resources import create_network, export_network_outputs
from storage_resources import create_storage, export_storage_outputs
from messaging_resources import create_messaging, export_messaging_outputs
from ssm_resources import create_worker_environment_ssm_parameters, export_worker_ssm_outputs
from pulumi_aws_modules.events import create_events


cfg = load_config()
prefix = cfg.project_prefix

storage = create_storage(prefix, tags=cfg.resource_tags)
export_storage_outputs(storage)

messaging = create_messaging(prefix, tags=cfg.resource_tags)
export_messaging_outputs(messaging)

database = create_database(prefix, tags=cfg.resource_tags)
export_database_outputs(database)

worker_ssm_path = create_worker_environment_ssm_parameters(
    prefix=prefix,
    messaging=messaging,
    worker_env_environment=pulumi.get_stack(),
    tags=cfg.resource_tags,
    aws_region=cfg.aws_region,
    confidence_threshold=cfg.confidence_threshold,
    model_stage1=cfg.model_stage1,
    model_stage2=cfg.model_stage2,
    work_dir=cfg.work_dir
)
export_worker_ssm_outputs(worker_ssm_path)

network = create_network(prefix, tags=cfg.resource_tags)
export_network_outputs(network)

identity = create_identity_resources(
    prefix=prefix,
    storage=storage,
    messaging=messaging,
    database=database,
    tags=cfg.resource_tags,
)
export_identity_outputs(identity)

# events = create_events(prefix, storage, messaging, database)

compute = create_compute_resources(
    prefix=prefix,
    network=network,
    messaging=messaging,
    identity=identity,
    min_size=cfg.asg_min_size,
    max_size=cfg.asg_max_size,
    instance_types=cfg.instance_types,
    worker_ami_id=cfg.worker_ami_id,
    worker_ami_ssm_parameter=cfg.worker_ami_ssm_parameter,
    spot_max_price=cfg.spot_max_price,
    scale_out_start_queue_depth=cfg.scale_out_start_queue_depth,
    queue_depth_step=cfg.queue_depth_step,
    tags=cfg.resource_tags,
)
export_compute_outputs(compute)

# pulumi.export("rawVideoBucketName", storage.raw_video_bucket.bucket)
# pulumi.export("evidenceBucketName", storage.evidence_bucket.bucket)
# pulumi.export("reportsBucketName", storage.reports_bucket.bucket)
# pulumi.export("ingestQueueUrl", messaging.ingest_queue.url)
# pulumi.export("stage2QueueUrl", messaging.stage2_queue.url)
# pulumi.export("ingestMetadataTableName", database.ingest_metadata_table.name)
# pulumi.export("detectionResultsTableName", database.detection_results_table.name)
# pulumi.export("metadataWriterLambdaName", events.metadata_lambda.name)
# pulumi.export("workerAsgName", compute.worker_asg.name)
# pulumi.export("sesSenderEmail", notifications.sender_identity.email)
