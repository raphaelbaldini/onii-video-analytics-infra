from dataclasses import dataclass

import pulumi_aws as aws


@dataclass(frozen=True)
class NotificationResources:
    sender_identity: aws.ses.EmailIdentity


def create_notifications(prefix: str, sender_email: str) -> NotificationResources:
    sender_identity = aws.ses.EmailIdentity(
        "ses-sender-identity",
        email=sender_email,
    )
    return NotificationResources(sender_identity=sender_identity)
