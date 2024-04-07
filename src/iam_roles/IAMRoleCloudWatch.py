import os
import boto3
import csv
from io import StringIO, BytesIO
import gzip
import concurrent.futures
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

# Define global variables
bucket_name = os.environ["CUR_s3_bucket_name"]
folder = os.environ["CUR_folder_name"]
file_key = os.environ["CUR_file_key"]
sender_email = os.environ["creator_email"]
recipient_email = os.environ["owner_email"]


def lambda_handler(event, context):
    iam_roles = list_iam_roles()
    lambda_functions = list_lambda_functions()
    lambda_role_mapping = create_lambda_role_mapping(lambda_functions)
    cost_data = generate_cost_data(
        iam_roles, lambda_role_mapping, bucket_name, file_key
    )
    push_metrics_to_prometheus_pushgateway(cost_data)
    send_email_with_cost_data(cost_data)


def list_iam_roles():
    iam_client = boto3.client("iam")
    iam_roles = []
    paginator = iam_client.get_paginator("list_roles")
    for page in paginator.paginate():
        for role in page["Roles"]:
            iam_roles.append({"RoleName": role["RoleName"], "RoleArn": role["Arn"]})
    return iam_roles


def list_lambda_functions():
    lambda_client = boto3.client("lambda")
    functions = []
    paginator = lambda_client.get_paginator("list_functions")
    for page in paginator.paginate():
        functions.extend(page["Functions"])
    return functions


def create_lambda_role_mapping(lambda_functions):
    mapping = {}
    for function in lambda_functions:
        mapping[function["FunctionName"]] = function["Role"]
    return mapping


def generate_cost_data(iam_roles, lambda_role_mapping, bucket_name, file_key):
    csv_content = download_and_decompress_csv(bucket_name, file_key)
    role_cost_data = {role["RoleName"]: 0.0 for role in iam_roles}

    def process_row(row):
        if row["lineItem/ProductCode"] == "AmazonCloudWatch":
            cost = float(row["lineItem/UnblendedCost"])
            resource_id = row["lineItem/ResourceId"]
            role_arn = extract_role_arn_from_resource_id(
                resource_id, lambda_role_mapping
            )
            if role_arn:
                role_name = get_role_name_from_arn(role_arn, iam_roles)
                if role_name in role_cost_data:
                    role_cost_data[role_name] += round(cost, 8)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        csv_reader = csv.DictReader(StringIO(csv_content))
        futures = [executor.submit(process_row, row) for row in csv_reader]
        concurrent.futures.wait(futures)

    return role_cost_data


def extract_role_arn_from_resource_id(resource_id, lambda_role_mapping):
    parts = resource_id.split(":")
    if (
        len(parts) >= 7
        and parts[2] == "logs"
        and parts[5] == "log-group"
        and parts[6].startswith("/aws/lambda/")
    ):
        lambda_function_name = parts[6].split("/")[-1]
        return lambda_role_mapping.get(lambda_function_name)
    return None


def get_role_arn_from_lambda_name(lambda_function_name, iam_roles):
    lambda_client = boto3.client("lambda")
    try:
        response = lambda_client.get_function(FunctionName=lambda_function_name)
        lambda_role_arn = response["Configuration"]["Role"]
        for role in iam_roles:
            if role["RoleArn"] == lambda_role_arn:
                return role["RoleArn"]
    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"Lambda function not found: {lambda_function_name}")
    return None


def get_role_name_from_arn(role_arn, iam_roles):
    for role in iam_roles:
        if role["RoleArn"] == role_arn:
            return role["RoleName"]
    return None


def download_and_decompress_csv(bucket_name, file_key):
    s3_client = boto3.client("s3")
    response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
    with gzip.GzipFile(fileobj=BytesIO(response["Body"].read())) as gz:
        file_content = gz.read().decode("utf-8")
    return file_content


def push_metrics_to_prometheus_pushgateway(cost_data):
    registry = CollectorRegistry()
    for role, cost in cost_data.items():
        gauge = Gauge(
            "aws_cloud_cost",
            "Cost of AWS Resources by Role",
            ["role"],
            registry=registry,
        )
        gauge.labels(role=role).set(cost)
    # Push the metrics to the Pushgateway
    push_to_gateway(
        os.environ["prometheus_ip"], job="aws_cloudwatch_costs", registry=registry
    )


def send_email_with_cost_data(cost_data):
    subject = "AmazonCloudWatch Cost Report"
    body = format_email_body(cost_data)
    send_email(sender_email, recipient_email, subject, body)


def format_email_body(cost_data):
    body = "AmazonCloudWatch Cost Report\n\n"
    for role, cost in cost_data.items():
        body += f"Role: {role}\nCost: ${cost:.8f}\n\n"
    return body


def send_email(sender, recipient, subject, body):
    ses_client = boto3.client("ses")
    try:
        response = ses_client.send_email(
            Destination={
                "ToAddresses": [recipient],
            },
            Message={
                "Body": {
                    "Text": {
                        "Charset": "UTF-8",
                        "Data": body,
                    },
                },
                "Subject": {
                    "Charset": "UTF-8",
                    "Data": subject,
                },
            },
            Source=sender,
        )
    except Exception as e:
        print(f"An error occurred: {e}")
    else:
        print("Email sent! Message ID:")
        print(response["MessageId"])
