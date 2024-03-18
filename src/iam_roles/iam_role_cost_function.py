import boto3
import json
from datetime import datetime, timedelta
import csv
from io import StringIO, BytesIO
import gzip
import os

def lambda_handler(event, context):
    iam_roles = list_iam_roles()
    role_function_mapping = map_roles_to_lambda_functions(iam_roles)
    bucket_name = 'team1reportbucket'
    file_key = 'report/mycostreport/20240301-20240401/20240315T100631Z/mycostreport-00001.csv.gz'
    cost_data = generate_cost_data(role_function_mapping, bucket_name, file_key)
    
    # Convert the cost_data to a string for email body
    email_body = json.dumps(cost_data, indent=4)
    
    # Send email
    sender_email = os.environ.get('creator_email')
    recipient_email = os.environ.get('owner_email')
    send_email(email_body, sender_email, recipient_email)
    
def send_email(email_body, sender_email, recipient_email):
    ses_client = boto3.client('ses')
    subject = 'AWS Lambda Cost Report'
    
    # Construct the email message
    email_message = f"""Subject: {subject}\n\n{email_body}"""
    
    # Send the email
    response = ses_client.send_email(
        Source=sender_email,
        Destination={
            'ToAddresses': [recipient_email],
        },
        Message={
            'Body': {
                'Text': {
                    'Charset': 'UTF-8',
                    'Data': email_message,
                },
            },
            'Subject': {
                'Charset': 'UTF-8',
                'Data': subject,
            },
        },
    )
    print("Email sent successfully.")


def list_iam_roles():
    iam_client = boto3.client('iam')
    iam_roles = []
    paginator = iam_client.get_paginator('list_roles')
    for page in paginator.paginate():
        for role in page['Roles']:
            iam_roles.append(role)
    return iam_roles

def map_roles_to_lambda_functions(iam_roles):
    lambda_client = boto3.client('lambda')
    role_function_mapping = []
    paginator = lambda_client.get_paginator('list_functions')
    for page in paginator.paginate():
        for function in page['Functions']:
            for role in iam_roles:
                if function['Role'] == role['Arn']:
                    role_function_mapping.append({'RoleName': role['RoleName'], 'RoleArn': role['Arn'], 'FunctionName': function['FunctionName']})
    return role_function_mapping

def generate_cost_data(role_function_mapping, bucket_name, file_key):
    csv_content = download_and_decompress_csv(bucket_name, file_key)
    csv_reader = csv.DictReader(StringIO(csv_content))
    # Initialize a dictionary to hold cost data for each role
    role_cost_data = {mapping['RoleName']: {'TotalCost': 0, 'Functions': {}} for mapping in role_function_mapping}
    for row in csv_reader:
        if row['lineItem/ProductCode'] == 'AWSLambda':
            function_arn = row['lineItem/ResourceId']
            cost = float(row['lineItem/UnblendedCost'])
            start_date = row['lineItem/UsageStartDate']
            # Find the corresponding role for the function ARN
            for mapping in role_function_mapping:
                if mapping['FunctionName'] in function_arn:  # Assuming FunctionName holds the ARN or part of it
                    role_name = mapping['RoleName']
                    function_name = mapping['FunctionName']
                    # Initialize function data if not present
                    if function_name not in role_cost_data[role_name]['Functions']:
                        role_cost_data[role_name]['Functions'][function_name] = {}
                    # Aggregate cost by start date
                    if start_date in role_cost_data[role_name]['Functions'][function_name]:
                        role_cost_data[role_name]['Functions'][function_name][start_date] += cost
                    else:
                        role_cost_data[role_name]['Functions'][function_name][start_date] = cost
                    # Update the total cost for the role
                    role_cost_data[role_name]['TotalCost'] += cost
                    break
    # Format cost values to non-scientific notation
    for role, data in role_cost_data.items():
        data['TotalCost'] = format(data['TotalCost'], '.8f')  # Format total cost
        for function_name, date_cost_map in data['Functions'].items():
            for date, cost in date_cost_map.items():
                role_cost_data[role]['Functions'][function_name][date] = format(cost, '.8f')  # Format cost for each date
    return role_cost_data



def download_and_decompress_csv(bucket_name, file_key):
    s3_client = boto3.client('s3')
    response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
    # Decompose the file content
    with gzip.GzipFile(fileobj=BytesIO(response['Body'].read())) as gz:
        file_content = gz.read().decode('utf-8')
    return file_content
