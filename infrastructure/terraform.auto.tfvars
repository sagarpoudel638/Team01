# Copyright (c) 2023, Xgrid Inc, https://xgrid.co

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#        http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

namespace      = "xc3abhishek1999191919"
env            = "dev"
region         = "ap-southeast-2"
account_id     = "211125640160"
vpc_cidr_block = "10.0.0.0/16"
public_subnet_cidr_block = {
  "ap-southeast-2a" = "10.0.0.0/24"
  "ap-southeast-2b" = "10.0.1.0/24"
}
domain_name    = ""
hosted_zone_id = ""

private_subnet_cidr_block = {
  "ap-southeast-2a" = "10.0.100.0/24"
}
# private_subnet_cidr_block  = "10.0.100.0/24"
allow_traffic               = ["0.0.0.0/0"] // Use your own network CIDR
ses_email_address           = "104057262@student.swin.edu.au"
creator_email               = "104057262@student.swin.edu.au"
owner_email                 = "104057262@student.swin.edu.au"
instance_type               = "t2.micro"
CUR_s3_bucket_name          = "team1reportbucket"
CUR_folder_name             = "report/mycostreport/20240301-20240401/"
CUR_file_key                = "20240315T100631Z/modified.gz"
iam_role_cloud_watch_function_lambda = "iam_role_cloud_watch_function"
iam_role_sns_function_lambda = "iam_role_sns_function"
iam_role_cost_function_lambda = "iam_role_cost_function"
total_account_cost_lambda   = "total_account_cost"
total_account_cost_cronjob  = "cron(0 0 1,15 * ? *)"     // flexible can be set according to need
prometheus_layer            = "lambda_layers/python.zip" // s3 key for lambda layer
memory_size                 = 128
timeout                     = 300
project                     = "xc3abhishek1999191919"
create_cloudtrail_kms       = false
create_cloudtrail           = false
create_cloudtrail_s3_bucket = false
security_group_ingress = {
  "pushgateway" = {
    description = "PushGateway"
    from_port   = 9091
    to_port     = 9091
    protocol    = "tcp"
    cidr_blocks = ["10.0.100.0/24"]
  },
  "prometheus" = {
    description = "Prometheus"
    from_port   = 9000
    to_port     = 9000
    protocol    = "tcp"
    cidr_blocks = ["10.0.100.0/24"]
  },
  "http" = {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["10.0.100.0/24"]
  },
  "https" = {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.100.0/24"]
  }
}
