import boto3
import json
from datetime import datetime
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON Encoder to convert datetime objects to strings."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)

def list_iam_roles():
    # Create an IAM client
    iam_client = boto3.client('iam')
    # Initialize a list to store all the IAM roles
    iam_roles = []
    
    # Use the IAM client to list roles
    paginator = iam_client.get_paginator('list_roles')
    
    for page in paginator.paginate():
        for role in page['Roles']:
            # Print out the role name
            # print(role['RoleName'])
            # Add the role to our list
            iam_roles.append(role)
    
    return iam_roles

def get_cost_for_iam_role(iam_role_name, start_time, end_time):
    # Create a Cost Explorer client
    ce_client = boto3.client('ce')
    # Retrieve cost metrics for the specified IAM role
    response = ce_client.get_cost_and_usage(
        TimePeriod={
            'Start': start_time,
            'End': end_time
        },
        Granularity='MONTHLY',
        Metrics=[
            'UnblendedCost'
        ],
        Filter={
            'Dimensions': {
                'Key': 'SERVICE',
                'Values': ['IAM Roles'],
            },
            'Tags': {
                'Key': 'RoleName',
                'Values': [iam_role_name],
            }
        }
    )
    # Extract and return the cost
    costs = response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount']
    return float(costs)

# Call the function to list IAM roles
roles = list_iam_roles()

# Optionally, you can print all the roles at once
# print(roles)

role_costs = {}

# Specify the start and end time for cost retrieval
start_time = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
end_time = datetime.utcnow().replace(day=1, month=start_time.month + 1, hour=0, minute=0, second=0, microsecond=0)

for role in roles:
    role_name = role['RoleName']
    role_cost = get_cost_for_iam_role(role_name, start_time, end_time)
    role_costs[role_name] = role_cost

# Optionally, you can print all the IAM roles with their costs
print(role_costs)

# Push data to Prometheus Push Gateway
def push_to_prometheus_gateway(role_costs):
    registry = CollectorRegistry()
    # Define a Prometheus Gauge metric
    iam_role_cost_metric = Gauge('iam_role_cost', 'Cost incurred by IAM roles', ['role_name'], registry=registry)
    
    # Push each IAM role cost to the metric
    for role_name, cost in role_costs.items():
        iam_role_cost_metric.labels(role_name=role_name).set(cost)
    
    # Push the metrics to the Prometheus Push Gateway
    push_to_gateway('your-prometheus-pushgateway-url', job='iam-role-cost', registry=registry)

# Call the function to push data to Prometheus Push Gateway
push_to_prometheus_gateway(role_costs)
