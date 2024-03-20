import boto3
from io import StringIO, BytesIO
import csv
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
        "aws_lambda_function_cost",
        "AWS Lambda function cost",
        ["role_name", "function_name", "start_date"],
        registry=registry,
    )
    # Iterate over the original cost_data to populate the metric
    for role_name, role_data in cost_data.items():
        for function_name, costs in role_data["Functions"].items():
            for cost_entry in costs:
                # Populate the Gauge with labels for role,
                # function, and start date, and set the cost as the value
                cost_gauge.labels(
                    role_name=role_name,
                    function_name=function_name,
                    start_date=cost_entry["StartDate"],
                ).set(cost_entry["Cost"])

    # Push the metrics to the Pushgateway
    push_to_gateway(
        os.environ["prometheus_ip"], job="aws_lambda_costs", registry=registry
    )

    # Send email with cost data
    send_email(cost_data)

    print("Data successfully processed.")

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

    # Initialize a dictionary to hold cost data for each role
    role_cost_data = {
        mapping["RoleName"]: {"TotalCost": 0, "Functions": {}}
        for mapping in role_function_mapping
    }

    for row in csv_reader:
        if row["lineItem/ProductCode"] == "AWSLambda":
            function_arn = row["lineItem/ResourceId"]
            cost = float(row["lineItem/UnblendedCost"])
            start_date = row["lineItem/UsageStartDate"]

            # Find the corresponding role for the function ARN
            for mapping in role_function_mapping:
                if (
                    mapping["FunctionName"] in function_arn
                ):  # Assuming FunctionName holds the ARN or part of it
                    role_name = mapping["RoleName"]
                    function_name = mapping["FunctionName"]

                    # Initialize function data if not present
                    if function_name not in role_cost_data[role_name]["Functions"]:
                        role_cost_data[role_name]["Functions"][function_name] = {}

                    # Aggregate cost by start date
                    if (
                        start_date
                        in role_cost_data[role_name]["Functions"][function_name]
                    ):
                        role_cost_data[role_name]["Functions"][function_name][
                            start_date
                        ] += cost
                    else:
                        role_cost_data[role_name]["Functions"][function_name][
                            start_date
                        ] = cost

                    # Update the total cost for the role
                    role_cost_data[role_name]["TotalCost"] += cost
                    break

    # Sort the function cost data by date and format it into a list
    for role, data in role_cost_data.items():
        for function_name, date_cost_map in data["Functions"].items():
            sorted_cost_data = [
                {"StartDate": date, "Cost": cost}
                for date, cost in sorted(date_cost_map.items())
            ]
            data["Functions"][function_name] = sorted_cost_data

    return role_cost_data

def download_and_decompress_csv(bucket_name, file_key):
    s3_client = boto3.client("s3")
    response = s3_client.get_object(Bucket=bucket_name, Key=file_key)

    # Decompose the file content
    with gzip.GzipFile(fileobj=BytesIO(response["Body"].read())) as gz:
        file_content = gz.read().decode("utf-8")

    return file_content

def send_email(cost_data):
    # Retrieve sender and recipient email addresses from environment variables
    sender_email = os.environ.get("creator_email")
    recipient_email = os.environ.get("owner_email")

    # Ensure sender and recipient email addresses are provided
    if not sender_email or not recipient_email:
        raise ValueError("Sender and/or recipient email addresses not provided.")

    # Define email parameters
    subject = "Lambda Function Costs Report"
    body = format_cost_data_for_email(cost_data)

    # Send email using Amazon SES
    ses_client = boto3.client('ses')
    ses_client.send_email(
        Source=sender_email,
        Destination={"ToAddresses": [recipient_email]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body}}
        }
    )

def format_cost_data_for_email(cost_data):
    # Format cost data for email body
    email_body = "Lambda Function Costs Report:\n\n"
    for role, data in cost_data.items():
        email_body += f"Role: {role}\n"
        email_body += f"Total Cost: ${data['TotalCost']:.8f}\n\n"
        email_body += "Functions:\n"
        for function_name, costs in data['Functions'].items():
            for cost_entry in costs:
                email_body += f"  - {function_name}: ${cost_entry['Cost']:.8f} ({cost_entry['StartDate']})\n"
        email_body += "\n"
    return email_body

