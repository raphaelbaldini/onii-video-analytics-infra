import json
import os
from datetime import datetime, timezone
from urllib.parse import unquote_plus

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def _record(bucket_name: str, object_key: str, event_time: str) -> dict:
    now = datetime.now(tz=timezone.utc)
    return {
        "videoId": f"{bucket_name}/{object_key}",
        "uploadedAt": event_time,
        "bucket": bucket_name,
        "objectKey": object_key,
        "status": "INGESTED",
        "ttl": int(now.timestamp()) + 30 * 24 * 60 * 60,
    }


def handler(event, _context):
    records = event.get("Records", [])
    for record in records:
        s3_obj = record["s3"]
        bucket_name = s3_obj["bucket"]["name"]
        object_key = unquote_plus(s3_obj["object"]["key"])
        event_time = record.get("eventTime", datetime.now(tz=timezone.utc).isoformat())
        table.put_item(Item=_record(bucket_name, object_key, event_time))

    return {"statusCode": 200, "body": json.dumps({"processed": len(records)})}
