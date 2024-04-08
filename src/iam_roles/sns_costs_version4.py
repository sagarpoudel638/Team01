import boto3
import csv
from io import StringIO, BytesIO
import gzip
import logging
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


def download_and_decompress_csv(bucket_name, file_key):
    """Download and decompress a gzip CSV file from S3."""
    s3_client = boto3.client("s3")
    response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
    gzip_file = gzip.GzipFile(fileobj=BytesIO(response["Body"].read()))
    csv_content = gzip_file.read().decode("utf-8")
    return csv_content


def extract_sns_costs(csv_content):
    """Extract SNS costs from CSV content."""
    sns_costs = {}
    reader = csv.DictReader(StringIO(csv_content))
    for row in reader:
        if row["lineItem/ProductCode"] == "AmazonSNS":
            topic_arn = row["lineItem/ResourceId"]
            cost = float(row["lineItem/UnblendedCost"])
            sns_costs[topic_arn] = sns_costs.get(topic_arn, 0) + cost
    return sns_costs


def list_lambda_functions():
    """List all Lambda functions and their execution roles."""
    lambda_client = boto3.client("lambda")
    paginator = lambda_client.get_paginator("list_functions")
    lambda_roles = {}

    for page in paginator.paginate():
        for func in page["Functions"]:
            lambda_roles[func["FunctionArn"]] = func["Role"]
    return lambda_roles


def is_valid_arn(arn):
    """Check if the provided ARN is in the correct format."""
    parts = arn.split(":")
    return len(parts) >= 6 and arn.startswith("arn:aws:sns:")


def get_sns_topic_subscriptions(topic_arns):
    """Get Lambda function subscriptions for given SNS topics."""
    sns_client = boto3.client("sns", region_name="ap-southeast-2")
    topic_subscriptions = {}

    for topic_arn in topic_arns:
        if not is_valid_arn(topic_arn):
            logger.error(f"Invalid ARN format: {topic_arn}")
            continue
        try:
            subscriptions = sns_client.list_subscriptions_by_topic(TopicArn=topic_arn)
            print("Subs: ", subscriptions)
            lambda_subs = [
                sub
                for sub in subscriptions["Subscriptions"]
                if sub["Protocol"] == "lambda"
            ]
            topic_subscriptions[topic_arn] = lambda_subs
        except sns_client.exceptions.NotFoundException:
            logger.error(f"Topic {topic_arn} does not exist or cannot be accessed.")

    return topic_subscriptions


def map_costs_to_roles(sns_costs, lambda_roles, topic_subscriptions):
    """Map SNS costs to IAM roles based on Lambda function subscriptions."""
    role_costs = {}

    for topic_arn, cost in sns_costs.items():
        if topic_arn not in topic_subscriptions:
            continue
        subscriptions = topic_subscriptions[topic_arn]
        cost_per_subscription = cost / len(subscriptions) if subscriptions else 0

        for sub in subscriptions:
            lambda_arn = sub["Endpoint"]
            if lambda_arn in lambda_roles:
                role_arn = lambda_roles[lambda_arn]
                if role_arn not in role_costs:
                    role_costs[role_arn] = 0
                role_costs[role_arn] += cost_per_subscription

    return role_costs


def push_metrics_to_prometheus_pushgateway(sns_costs):
    """Prepare and push SNS cost metrics to Prometheus Pushgateway."""
    registry = CollectorRegistry()
    gauge = Gauge(
        "aws_sns_cost", "Cost of AWS SNS by Topic ARN", ["topic_arn"], registry=registry
    )

    for topic_arn, cost in sns_costs.items():
        gauge.labels(topic_arn=topic_arn).set(cost)
        push_to_gateway(
            os.environ["prometheus_ip"], job="aws_sns_costs", registry=registry
        )
        logger.info(f"Prepared metric for topic {topic_arn} with cost {cost}")


def lambda_handler(event, context):
    bucket_name = "team1reportbucket"
    file_key = "report/mycostreport/20240301-20240401/20240315T100631Z/modified.gz"

    csv_content = download_and_decompress_csv(bucket_name, file_key)
    sns_costs = extract_sns_costs(csv_content)

    push_metrics_to_prometheus_pushgateway(sns_costs)

    sns_cost_details = [
        {"Topic ARN": arn, "Cost": f"${cost:.2f}"} for arn, cost in sns_costs.items()
    ]

    response_body = {
        "statusCode": 200,
        "body": "Successfully processed SNS cost metrics and prepared for Grafana.",
        "details": sns_cost_details,
    }

    return response_body


# Example call for local testing or manual invocation
if __name__ == "__main__":
    result = lambda_handler({}, {})
    # print(result)
