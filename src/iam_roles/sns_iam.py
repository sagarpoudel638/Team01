import boto3
import csv
from io import StringIO, BytesIO
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
import gzip
import os

def lambda_handler(event, context):
    iam_roles = list_iam_roles()
    cost_data = generate_cost_data(iam_roles)
    print(cost_data)  # Debug statement
    registry = CollectorRegistry()
    
    # Define the metric
    sns_cost_gauge = Gauge(
        "sns_role_cost",
        "AWS SNS role cost",
        ["role_name", "start_date"],
        registry=registry,
    )
    # Iterate over the original cost_data to populate the metric
    for role_name, costs in cost_data.items():
        for cost_entry in costs["CostEntries"]:  # Access the "CostEntries" list from the dictionary
            # Populate the Gauge with labels for role name and start date,
            # and set the cost as the value
            sns_cost_gauge.labels(
                role_name=role_name,
                start_date=cost_entry["StartDate"],
            ).set(cost_entry["Cost"])
    # Push the metrics to the Pushgateway
    push_to_gateway(
        os.environ["prometheus_ip"], job="aws_sns_role_costs", registry=registry
    )
    print("Data successfully pushed to Prometheus Pushgateway.")



def list_iam_roles():
    iam_client = boto3.client("iam")
    iam_roles = []
    paginator = iam_client.get_paginator("list_roles")
    for page in paginator.paginate():
        for role in page["Roles"]:
            iam_roles.append(role["RoleName"])
    return iam_roles

def generate_cost_data(iam_roles):
    bucket_name = "team1reportbucket"
    folder = "report/mycostreport/20240301-20240401/"
    file_key = folder + "20240315T100631Z/mycostreport-00001.csv.gz"
    csv_content = download_and_decompress_csv(bucket_name, file_key)
    csv_reader = csv.DictReader(StringIO(csv_content))
    # Initialize a dictionary to hold total cost data for each IAM role
    role_cost_data = {role_name: {"TotalCost": 0, "CostEntries": []} for role_name in iam_roles}

    for row in csv_reader:
        if row["lineItem/ProductCode"] == "AmazonSNSS":
            function_arn = row["lineItem/ResourceId"]
            cost = float(row["lineItem/UnblendedCost"])
            start_date = row["lineItem/UsageStartDate"]
            # Find the corresponding role for the function ARN
            for role_name in iam_roles:
                if role_name in function_arn:
                    # Add cost entry to the corresponding IAM role
                    role_cost_data[role_name]["CostEntries"].append({"StartDate": start_date, "Cost": cost})
                    # Aggregate cost for the IAM role
                    role_cost_data[role_name]["TotalCost"] += cost
                    break

    return role_cost_data



def download_and_decompress_csv(bucket_name, file_key):
    s3_client = boto3.client("s3")
    response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
    # Decompose the file content
    with gzip.GzipFile(fileobj=BytesIO(response["Body"].read())) as gz:
        file_content = gz.read().decode("utf-8")
    return file_content
