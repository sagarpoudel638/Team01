import boto3
import csv
from io import StringIO


def download_and_parse_csv(s3_client, bucket_name, file_key):
    """Download and parse CSV file from S3."""
    response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
    csv_string = response["Body"].read().decode("utf-8")
    return list(csv.DictReader(StringIO(csv_string)))


def fetch_lambda_to_role_mapping(lambda_client):
    """Fetch mapping from Lambda ARNs to IAM Role ARNs."""
    mapping = {}
    paginator = lambda_client.get_paginator("list_functions")
    for page in paginator.paginate():
        for function in page["Functions"]:
            mapping[function["FunctionArn"]] = function["Role"]
    return mapping


def fetch_topic_subscriptions(sns_client, topic_arns):
    """Fetch subscriptions for given SNS topics."""
    mapping = {}
    for topic_arn in topic_arns:
        if not topic_arn.startswith("arn:aws:sns:"):
            print(f"Invalid ARN skipped: {topic_arn}")
            continue
        try:
            subscriptions = sns_client.list_subscriptions_by_topic(TopicArn=topic_arn)[
                "Subscriptions"
            ]
            mapping[topic_arn] = [
                sub["Endpoint"] for sub in subscriptions if sub["Protocol"] == "lambda"
            ]
        except sns_client.exceptions.NotFoundException:
            print(f"Topic {topic_arn} not found. Skipping...")
        except Exception as e:
            print(f"An error occurred: {e}")
    return mapping


def map_costs_to_roles(csv_rows, lambda_to_role_mapping, topic_subscriptions):
    """Map costs to IAM roles based on Lambda functions and SNS subscriptions."""
    role_costs = {}
    for row in csv_rows:
        product_code = row["lineItem/ProductCode"]
        resource_id = row["lineItem/ResourceId"]
        cost = float(row["lineItem/UnblendedCost"])

        if product_code == "AWSLambda":
            if resource_id in lambda_to_role_mapping:
                role_arn = lambda_to_role_mapping[resource_id]
                role_costs[role_arn] = role_costs.get(role_arn, 0) + cost
        elif product_code == "AmazonSNS":
            if resource_id in topic_subscriptions:
                for lambda_arn in topic_subscriptions[resource_id]:
                    if lambda_arn in lambda_to_role_mapping:
                        role_arn = lambda_to_role_mapping[lambda_arn]
                        role_costs[role_arn] = role_costs.get(role_arn, 0) + cost
    return role_costs


def main(bucket_name, file_key):
    s3_client = boto3.client("s3")
    lambda_client = boto3.client("lambda")
    sns_client = boto3.client("sns")

    csv_rows = download_and_parse_csv(s3_client, bucket_name, file_key)
    lambda_to_role_mapping = fetch_lambda_to_role_mapping(lambda_client)

    sns_topic_arns = {
        row["lineItem/ResourceId"]
        for row in csv_rows
        if row["lineItem/ProductCode"] == "AmazonSNS"
    }
    print("SNS Topic ARNs:", sns_topic_arns)
    topic_subscriptions = fetch_topic_subscriptions(sns_client, sns_topic_arns)

    role_costs = map_costs_to_roles(
        csv_rows, lambda_to_role_mapping, topic_subscriptions
    )

    for role_arn, cost in role_costs.items():
        print(f"Role ARN: {role_arn}, Total Cost: {cost}")


# Example usage - replace 'your-bucket-name' and 'your-file-key' with actual values
bucket_name = "team1reportbucket"
file_key = (
    "report/mycostreport/20240401-20240501/20240405T101631Z/mycostreport-00001.csv"
)
main(bucket_name, file_key)
