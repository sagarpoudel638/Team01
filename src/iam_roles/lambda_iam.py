#I updated Lambda. But the logic was wrong and the data structure wasnt correct for sending to grafana
import boto3
# import json
# from datetime import datetime, timedelta
import csv
from io import StringIO, BytesIO
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
import gzip
import os

def lambda_handler(event, context):
    iam_roles = list_iam_roles()
    role_function_mapping = map_roles_to_lambda_functions(iam_roles)
    bucket_name = "team1reportbucket"
    folder = "report/mycostreport/20240301-20240401/"
    file_key = folder + "20240315T100631Z/mycostreport-00001.csv.gz"
    cost_data = generate_cost_data(role_function_mapping, bucket_name, file_key)
    print(cost_data)
    registry = CollectorRegistry()
    # Define the metric
    cost_gauge = Gauge(
    "aws_service_cost",
    "Cost of AWS services by role and function",
    ["role_name", "service_name", "function_name", "start_date"],
    registry=registry,)

    # Iterate over the original cost_data to populate the metric
    # Iterate over the updated cost_data to populate the metric
    for role_name, role_data in cost_data.items():
        for service_name, service_data in role_data["Services"].items():
            for function_name, costs in service_data["Functions"].items():
                for cost_entry in costs:
                    # Populate the Gauge with labels for role, service, function, and start date,
                    # and set the cost as the value
                    cost_gauge.labels(
                        role_name=role_name,
                        service_name=service_name,
                        function_name=function_name,
                        start_date=cost_entry["StartDate"],
                    ).set(cost_entry["Cost"])


    # Push the metrics to the Pushgateway
    push_to_gateway(
        os.environ["prometheus_ip"], job="aws_service_costs", registry=registry
    )

    print("Data successfully pushed to Prometheus Pushgateway.")

def list_iam_roles():
    iam_client = boto3.client("iam")
    iam_roles = []
    paginator = iam_client.get_paginator("list_roles")
    for page in paginator.paginate():
        for role in page["Roles"]:
            iam_roles.append(role)
    return iam_roles

def map_roles_to_lambda_functions(iam_roles):
    lambda_client = boto3.client("lambda")
    role_function_mapping = []
    paginator = lambda_client.get_paginator("list_functions")
    for page in paginator.paginate():
        for function in page["Functions"]:
            for role in iam_roles:
                if function["Role"] == role["Arn"]:
                    role_function_mapping.append(
                        {
                            "RoleName": role["RoleName"],
                            "RoleArn": role["Arn"],
                            "FunctionName": function["FunctionName"],
                        }
                    )
    return role_function_mapping

def generate_cost_data(role_function_mapping, bucket_name, file_key):
    csv_content = download_and_decompress_csv(bucket_name, file_key)
    csv_reader = csv.DictReader(StringIO(csv_content))
    # Initialize a dictionary to hold cost data for each role, now including a 'Services' key
    role_cost_data = {
        mapping["RoleName"]: {"TotalCost": 0, "Services": {}}
        for mapping in role_function_mapping
    }
    for row in csv_reader:
        # Example for AWS Lambda, adjust the condition and parsing for other services
        if row["lineItem/ProductCode"] == "AWSLambda":
            service_name = "Lambda"  # Identify the service name, dynamic based on the service
            function_arn = row["lineItem/ResourceId"]
            cost = float(row["lineItem/UnblendedCost"])
            start_date = row["lineItem/UsageStartDate"]
            # Find the corresponding role for the function ARN
            for mapping in role_function_mapping:
                if mapping["FunctionName"] in function_arn:  # Matching function by ARN
                    role_name = mapping["RoleName"]
                    function_name = mapping["FunctionName"]
                    # Initialize service and function data if not present
                    service_data = role_cost_data[role_name].setdefault("Services", {}).setdefault(service_name, {"TotalCost": 0, "Functions": {}})
                    function_data = service_data["Functions"].setdefault(function_name, [])
                    # Append cost entry
                    function_data.append({"StartDate": start_date, "Cost": cost})
                    # Update the total cost for the role and the service
                    role_cost_data[role_name]["TotalCost"] += cost
                    service_data["TotalCost"] += cost
                    break

    # After processing all rows, optionally sort the function cost data by date within each service
    for role_name, role_data in role_cost_data.items():
        for service_name, service_data in role_data["Services"].items():
            for function_name, costs in service_data["Functions"].items():
                service_data["Functions"][function_name] = sorted(costs, key=lambda x: x["StartDate"])

    return role_cost_data


def download_and_decompress_csv(bucket_name, file_key):
    s3_client = boto3.client("s3")
    response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
    # Decompose the file content
    with gzip.GzipFile(fileobj=BytesIO(response["Body"].read())) as gz:
        file_content = gz.read().decode("utf-8")
    return file_content