import pulumi
import pulumi_aws as aws


def create_queue_depth_scaling(
    prefix: str,
    resource_name: str,
    asg: aws.autoscaling.Group,
    queue_name: pulumi.Input[str],
    max_size: int,
    scale_out_start_queue_depth: int,
    queue_depth_step: int,
) -> None:
    bounded_max_size = max(1, max_size)
    bounded_step = max(1, queue_depth_step)
    bounded_scale_out_start = max(1, scale_out_start_queue_depth)
    alarm_name_prefix = (
        f"{prefix}-queue-depth"
        if resource_name == "video-worker"
        else f"{prefix}-{resource_name}-queue-depth"
    )

    step_adjustments: list[aws.autoscaling.PolicyStepAdjustmentArgs] = []
    for target_capacity in range(1, bounded_max_size + 1):
        lower_bound = float((target_capacity - 1) * bounded_step)
        upper_bound = (
            float(target_capacity * bounded_step) if target_capacity < bounded_max_size else None
        )
        kwargs: dict[str, float | int] = {
            "metric_interval_lower_bound": lower_bound,
            "scaling_adjustment": target_capacity,
        }
        if upper_bound is not None:
            kwargs["metric_interval_upper_bound"] = upper_bound
        step_adjustments.append(aws.autoscaling.PolicyStepAdjustmentArgs(**kwargs))

    scale_up_policy = aws.autoscaling.Policy(
        f"{resource_name}-scale-up",
        name=f"{prefix}-{resource_name}-scale-up",
        autoscaling_group_name=asg.name,
        policy_type="StepScaling",
        adjustment_type="ChangeInCapacity",
        metric_aggregation_type="Average",
        step_adjustments=step_adjustments,
    )

    scale_to_one_policy = aws.autoscaling.Policy(
        f"{resource_name}-scale-to-one",
        name=f"{prefix}-{resource_name}-scale-to-one",
        autoscaling_group_name=asg.name,
        adjustment_type="ExactCapacity",
        scaling_adjustment=1,
        cooldown=180,
    )

    scale_down_policy = aws.autoscaling.Policy(
        f"{resource_name}-scale-down",
        name=f"{prefix}-{resource_name}-scale-down",
        autoscaling_group_name=asg.name,
        adjustment_type="ChangeInCapacity",
        scaling_adjustment=-1,
        cooldown=300,
    )

    queue_depth_queries = [
        aws.cloudwatch.MetricAlarmMetricQueryArgs(
            id="queueDepth",
            return_data=False,
            metric=aws.cloudwatch.MetricAlarmMetricQueryMetricArgs(
                metric_name="ApproximateNumberOfMessagesVisible",
                namespace="AWS/SQS",
                period=60,
                stat="Average",
                dimensions={"QueueName": queue_name},
            ),
        ),
        aws.cloudwatch.MetricAlarmMetricQueryArgs(
            id="totalDepth",
            expression="queueDepth",
            label="TotalQueueDepth",
            return_data=True,
        ),
    ]

    aws.cloudwatch.MetricAlarm(
        f"{resource_name}-queue-depth-high",
        name=f"{alarm_name_prefix}-high",
        comparison_operator="GreaterThanOrEqualToThreshold",
        threshold=bounded_scale_out_start,
        evaluation_periods=2,
        datapoints_to_alarm=2,
        treat_missing_data="notBreaching",
        alarm_actions=[scale_up_policy.arn],
        metric_queries=queue_depth_queries,
    )

    low_backlog_queries = [
        aws.cloudwatch.MetricAlarmMetricQueryArgs(
            id="queueDepth",
            return_data=False,
            metric=aws.cloudwatch.MetricAlarmMetricQueryMetricArgs(
                metric_name="ApproximateNumberOfMessagesVisible",
                namespace="AWS/SQS",
                period=60,
                stat="Average",
                dimensions={"QueueName": queue_name},
            ),
        ),
        aws.cloudwatch.MetricAlarmMetricQueryArgs(
            id="totalDepth",
            expression="queueDepth",
            label="TotalQueueDepthLowBacklog",
            return_data=False,
        ),
        aws.cloudwatch.MetricAlarmMetricQueryArgs(
            id="lowBacklogWork",
            expression=(
                f"IF(totalDepth < {bounded_scale_out_start}, IF(totalDepth > 0, 1, 0), 0)"
            ),
            label="LowBacklogWork",
            return_data=True,
        )
    ]

    aws.cloudwatch.MetricAlarm(
        f"{resource_name}-queue-depth-low-backlog",
        name=f"{alarm_name_prefix}-low-backlog",
        comparison_operator="GreaterThanOrEqualToThreshold",
        threshold=1,
        evaluation_periods=3,
        datapoints_to_alarm=3,
        treat_missing_data="notBreaching",
        alarm_actions=[scale_to_one_policy.arn],
        metric_queries=low_backlog_queries,
    )

    aws.cloudwatch.MetricAlarm(
        f"{resource_name}-queue-depth-idle",
        name=f"{alarm_name_prefix}-idle",
        comparison_operator="LessThanThreshold",
        threshold=1,
        evaluation_periods=10,
        datapoints_to_alarm=10,
        treat_missing_data="breaching",
        alarm_actions=[scale_down_policy.arn],
        metric_queries=queue_depth_queries,
    )

