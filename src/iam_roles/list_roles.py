import boto3
import json
from datetime import datetime

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

# Call the function to list IAM roles
roles = list_iam_roles()

# Optionally, you can print all the roles at once
# print(roles)

with open('iam_roles.json', 'w') as f:
    json.dump(roles, f, cls=DateTimeEncoder, indent=4)