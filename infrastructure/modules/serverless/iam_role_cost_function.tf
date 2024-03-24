data "archive_file" "iam_role_cost_function" {
  type        = "zip"
  source_file = "../src/iam_roles/iam_role_cost_function.py"
  output_path = "${path.module}/iam_role_cost_function.zip"
}

# Creating IAM Role for Lambda functions
resource "aws_iam_role" "iam_role_cost_function" {
  name = "${var.namespace}-${var.iam_role_cost_function_lambda}-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Sid    = "IAMRoleCostFunction"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  managed_policy_arns = ["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]
  tags                = merge(local.tags, tomap({ "Name" = "${var.namespace}-iam_role_cost_function" }))
}

resource "aws_iam_role_policy" "iam_role_cost_function" {
  name = "${var.namespace}-${var.iam_role_cost_function_lambda}-ce-policy"
  role = aws_iam_role.iam_role_cost_function.id
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Sid" : "S3GetObject",
        "Effect" : "Allow",
        "Action" : [
          "s3:GetObject"
        ],
        "Resource" : "arn:aws:s3:::team1reportbucket/*"
      },
      {
        "Sid" : "SendEmail",
        "Effect" : "Allow",
        "Action" : [
          "ses:SendEmail"
        ],
        "Resource" : "*"
      },
      {
        "Sid" : "ListIAMRoles",
        "Effect" : "Allow",
        "Action" : [
          "iam:ListRoles"
        ],
        "Resource" : "*"
      },
      {
        "Sid": "IAMRoleCost",
        "Effect": "Allow",
        "Action": [
          "ce:GetCostAndUsage",
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DetachNetworkInterface",
          "ec2:AttachNetworkInterface",
          "ec2:DeleteNetworkInterface"
        ],
        "Resource": "*"
      },
      {
        "Sid": "SSMParameter",
        "Effect": "Allow",
        "Action": [
          "ssm:GetParameter"
        ],
        "Resource": "arn:aws:ssm:*:*:parameter/*"
      },
      {
        "Sid" : "ListLambdaFunctions",
        "Effect" : "Allow",
        "Action" : [
          "lambda:ListFunctions"
        ],
        "Resource" : "*"
      }
    ]
  })
}

resource "aws_lambda_function" "iam_role_cost_function" {
  function_name = "${var.namespace}-${var.iam_role_cost_function_lambda}"
  role          = aws_iam_role.iam_role_cost_function.arn
  runtime       = "python3.9"
  handler       = "${var.iam_role_cost_function_lambda}.lambda_handler"
  filename      = data.archive_file.iam_role_cost_function.output_path
  environment {
    variables = {
      prometheus_ip  = "${var.prometheus_ip}:9091"
      account_detail = var.namespace
      creator_email    = var.creator_email
      owner_email = var.owner_email
      CUR_s3_bucket_name = var.CUR_s3_bucket_name
      CUR_folder_name = var.CUR_folder_name
      CUR_file_key = var.CUR_file_key
    }
  }
  memory_size = var.memory_size
  timeout     = var.timeout
  layers      = [var.prometheus_layer]
  vpc_config {
    subnet_ids         = [var.subnet_id[0]]
    security_group_ids = [var.security_group_id]
  }
  tags = merge(local.tags, tomap({ "Name" = "${var.namespace}-iam_role_cost_function" }))
}

resource "aws_iam_policy" "iam_role_cost_function" {
  name = "${var.namespace}-iam_role_cost_function_eventbridge_policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "lambda:InvokeFunction"
        ]
        Effect   = "Allow"
        Resource = aws_lambda_function.iam_role_cost_function.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "iam_role_cost_function" {
  policy_arn = aws_iam_policy.iam_role_cost_function.arn
  role       = aws_iam_role.iam_role_cost_function.name
}