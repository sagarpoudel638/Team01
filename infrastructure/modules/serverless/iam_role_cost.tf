data "archive_file" "iam_role_cost" {
  type        = "zip"
  source_file = "../src/iam_roles/iam_role_cost.py"
  output_path = "${path.module}/iam_role_cost.zip"
}

# Creating IAM Role for Lambda functions
resource "aws_iam_role" "iam_role_cost" {
  name = "${var.namespace}-${var.iam_role_cost_lambda}-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Sid    = "IAMRoleSNSFunction"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  managed_policy_arns = ["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]
  tags                = merge(local.tags, tomap({ "Name" = "${var.namespace}-iam_role_cost" }))
}

resource "aws_iam_role_policy" "iam_role_cost" {
  name = "${var.namespace}-${var.iam_role_cost_lambda}-ce-policy"
  role = aws_iam_role.iam_role_cost.id
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
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
        "Effect" : "Allow",
        "Action" : [
          "s3:GetObject"
        ],
        "Resource" : "arn:aws:s3:::${var.CUR_s3_bucket_name}/*" 
      },
        {
            "Effect": "Allow",
            "Action": [
                "SNS:ListSubscriptionsByTopic"],
            "Resource": "*"
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

resource "aws_lambda_function" "iam_role_cost" {
  function_name = "${var.namespace}-${var.iam_role_cost_lambda}"
  role          = aws_iam_role.iam_role_cost.arn
  runtime       = "python3.9"
  handler       = "${var.iam_role_cost_lambda}.lambda_handler"
  filename      = data.archive_file.iam_role_cost.output_path
  environment {
    variables = {
      prometheus_ip  = "${var.prometheus_ip}:9091"
      account_detail = var.namespace
      creator_email    = var.creator_email
      owner_email = var.owner_email
      CUR_s3_bucket_name = var.CUR_s3_bucket_name
      CUR_s3_file_key = var.CUR_s3_file_key
    }
  }
  memory_size = var.memory_size
  timeout     = var.timeout
  layers      = [var.prometheus_layer]
  vpc_config {
    subnet_ids         = [var.subnet_id[0]]
    security_group_ids = [var.security_group_id]
  }
  tags = merge(local.tags, tomap({ "Name" = "${var.namespace}-iam_role_cost" }))
}

resource "aws_iam_policy" "iam_role_cost" {
  name = "${var.namespace}-iam_role_cost_eventbridge_policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "lambda:InvokeFunction"
        ]
        Effect   = "Allow"
        Resource = aws_lambda_function.iam_role_cost.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "iam_role_cost" {
  policy_arn = aws_iam_policy.iam_role_cost.arn
  role       = aws_iam_role.iam_role_cost.name
}