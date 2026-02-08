provider "aws" {
  region = var.aws_region
}

# SSM Parameters for API Keys (placeholders - set manually in AWS Console)
resource "aws_ssm_parameter" "openai_api_key" {
  name        = "/${var.app_name}/openai-api-key"
  description = "OpenAI API Key for ${var.app_name}"
  type        = "SecureString"
  value       = "PLACEHOLDER_CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    Name        = "${var.app_name}-openai-api-key"
    Application = var.app_name
  }
}

resource "aws_ssm_parameter" "mistral_api_key" {
  name        = "/${var.app_name}/mistral-api-key"
  description = "Mistral API Key for ${var.app_name}"
  type        = "SecureString"
  value       = "PLACEHOLDER_CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    Name        = "${var.app_name}-mistral-api-key"
    Application = var.app_name
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
    Name        = "${var.app_name}-lambda-role"
    Application = var.app_name
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
      }
    ]
  })
}

# Lambda function using container image
resource "aws_lambda_function" "app" {
  function_name = var.app_name
  role          = aws_iam_role.lambda_execution_role.arn
  package_type  = "Image"
  image_uri     = var.image_identifier
  timeout       = 300
  memory_size   = 1024

  environment {

    variables = {
      MODEL_PROVIDER  = var.model_provider
      MODEL_NAME      = var.model_name
      # SSM parameter names (start with '/') - secrets_manager.py will auto-detect and retrieve from SSM
      OPENAI_API_KEY  = aws_ssm_parameter.openai_api_key.name
      MISTRAL_API_KEY = aws_ssm_parameter.mistral_api_key.name
    }
  }

  tags = {
    Name        = var.app_name
    Application = var.app_name
  }
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.app_name}"
  retention_in_days = 7

  tags = {
    Name        = "${var.app_name}-logs"
    Application = var.app_name
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
    Name        = "${var.app_name}-api"
    Application = var.app_name
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
    Name        = "${var.app_name}-stage"
    Application = var.app_name
  }
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/apigateway/${var.app_name}"
  retention_in_days = 7

  tags = {
    Name        = "${var.app_name}-api-logs"
    Application = var.app_name
  }
}

# Lambda Integration with API Gateway
resource "aws_apigatewayv2_integration" "lambda" {
  api_id             = aws_apigatewayv2_api.api.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.app.invoke_arn
  integration_method = "POST"
  payload_format_version = "2.0"
}

# API Gateway Route (catch-all)
resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Lambda permission for API Gateway to invoke
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.app.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}
