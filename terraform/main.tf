terraform {
  backend "s3" {
    bucket       = "patient-insight-tf-state-production"
    key          = "terraform.tfstate"
    region       = "eu-west-3"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Application = var.app_name
      Environment = "production"
    }
  }
}

# KMS key for encrypting SSM parameters, CloudWatch Logs, and SQS
resource "aws_kms_key" "app" {
  description             = "KMS key for ${var.app_name} encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableRootAccountAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowCloudWatchLogs"
        Effect = "Allow"
        Principal = {
          Service = "logs.${var.aws_region}.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name = "${var.app_name}-kms-key"
  }
}

resource "aws_kms_alias" "app" {
  name          = "alias/${var.app_name}-production"
  target_key_id = aws_kms_key.app.key_id
}

data "aws_caller_identity" "current" {}

# SSM Parameters for API Keys (placeholders - set manually in AWS Console)
resource "aws_ssm_parameter" "openai_api_key" {
  name        = "/${var.app_name}/openai-api-key"
  description = "OpenAI API Key for ${var.app_name}"
  type        = "SecureString"
  key_id      = aws_kms_key.app.arn
  value       = "PLACEHOLDER_CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    Name = "${var.app_name}-openai-api-key"
  }
}

resource "aws_ssm_parameter" "mistral_api_key" {
  name        = "/${var.app_name}/mistral-api-key"
  description = "Mistral API Key for ${var.app_name}"
  type        = "SecureString"
  key_id      = aws_kms_key.app.arn
  value       = "PLACEHOLDER_CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    Name = "${var.app_name}-mistral-api-key"
  }
}

# IAM Role for Lambda execution
resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.app_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.app_name}-lambda-role"
  }
}

# Attach basic Lambda execution policy (for CloudWatch Logs)
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Policy to allow Lambda to read SSM parameters
resource "aws_iam_role_policy" "lambda_ssm_policy" {
  name = "${var.app_name}-lambda-ssm-access"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = [
          aws_ssm_parameter.openai_api_key.arn,
          aws_ssm_parameter.mistral_api_key.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = [
          aws_kms_key.app.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = [
          aws_sqs_queue.lambda_dlq.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability"
        ]
        Resource = [
          "arn:aws:ecr:${var.aws_region}:${data.aws_caller_identity.current.account_id}:repository/${var.app_name}"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = ["*"]
      }
    ]
  })
}

# Policy to allow Lambda to write X-Ray traces
resource "aws_iam_role_policy_attachment" "lambda_xray" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

# SQS Dead Letter Queue for Lambda
resource "aws_sqs_queue" "lambda_dlq" {
  name                      = "${var.app_name}-lambda-dlq"
  kms_master_key_id         = aws_kms_key.app.arn
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name = "${var.app_name}-lambda-dlq"
  }
}

# Lambda function using container image
resource "aws_lambda_function" "app" {
  # checkov:skip=CKV_AWS_272:Code signing is not supported for container image Lambda functions
  function_name                  = var.app_name
  role                           = aws_iam_role.lambda_execution_role.arn
  package_type                   = "Image"
  image_uri                      = var.image_identifier
  timeout                        = 300
  memory_size                    = 1024
  reserved_concurrent_executions = var.lambda_reserved_concurrency

  tracing_config {
    mode = "Active"
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.lambda_dlq.arn
  }

  environment {

    variables = {
      MODEL_PROVIDER = var.model_provider
      MODEL_NAME     = var.model_name
      # SSM parameter names (start with '/') - secrets_manager.py will auto-detect and retrieve from SSM
      OPENAI_API_KEY  = aws_ssm_parameter.openai_api_key.name
      MISTRAL_API_KEY = aws_ssm_parameter.mistral_api_key.name
    }
  }

  tags = {
    Name = var.app_name
  }
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.app_name}"
  retention_in_days = 365
  kms_key_id        = aws_kms_key.app.arn

  tags = {
    Name = "${var.app_name}-logs"
  }
}

# API Gateway HTTP API
resource "aws_apigatewayv2_api" "api" {
  name          = "${var.app_name}-api"
  protocol_type = "HTTP"
  description   = "HTTP API for ${var.app_name}"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["*"]
    max_age       = 300
  }

  tags = {
    Name = "${var.app_name}-api"
  }
}

# API Gateway Stage
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }

  tags = {
    Name = "${var.app_name}-stage"
  }
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/apigateway/${var.app_name}"
  retention_in_days = 365
  kms_key_id        = aws_kms_key.app.arn

  tags = {
    Name = "${var.app_name}-api-logs"
  }
}

# Lambda Integration with API Gateway
resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.app.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

# API Gateway Route (catch-all)
resource "aws_apigatewayv2_route" "default" {
  api_id             = aws_apigatewayv2_api.api.id
  route_key          = "$default"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "AWS_IAM"
}

# Lambda permission for API Gateway to invoke
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.app.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}
