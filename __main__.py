import pulumi

from config import load_config
from modules.compute import create_compute
from modules.database import create_database
from modules.events import create_events
from modules.messaging import create_messaging
from modules.network import create_network
from modules.notifications import create_notifications
from modules.storage import create_storage


cfg = load_config()
prefix = cfg.project_prefix

storage = create_storage(prefix)
messaging = create_messaging(prefix)
database = create_database(prefix)
network = create_network(prefix)
events = create_events(prefix, storage, messaging, database)
notifications = create_notifications(prefix, cfg.customer_notification_email)
compute = create_compute(
    prefix=prefix,
    network=network,
    storage=storage,
    messaging=messaging,
    database=database,
    min_size=cfg.asg_min_size,
    max_size=cfg.asg_max_size,
    instance_types=cfg.instance_types,
    worker_ami_id=cfg.worker_ami_id,
    worker_ami_ssm_parameter=cfg.worker_ami_ssm_parameter,
)

pulumi.export("rawVideoBucketName", storage.raw_video_bucket.bucket)
pulumi.export("evidenceBucketName", storage.evidence_bucket.bucket)
pulumi.export("reportsBucketName", storage.reports_bucket.bucket)
pulumi.export("ingestQueueUrl", messaging.ingest_queue.url)
pulumi.export("stage2QueueUrl", messaging.stage2_queue.url)
pulumi.export("ingestMetadataTableName", database.ingest_metadata_table.name)
pulumi.export("detectionResultsTableName", database.detection_results_table.name)
pulumi.export("metadataWriterLambdaName", events.metadata_lambda.name)
pulumi.export("workerAsgName", compute.worker_asg.name)
pulumi.export("sesSenderEmail", notifications.sender_identity.email)
