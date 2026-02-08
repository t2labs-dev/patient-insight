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

# IAM Role for App Runner to access ECR
resource "aws_iam_role" "app_runner_access_role" {
  name = "${var.app_name}-app-runner-access-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "build.apprunner.amazonaws.com"
        }
      },
    ]
  })

  tags = {
    Name        = "${var.app_name}-access-role"
    Application = var.app_name
  }
}

resource "aws_iam_role_policy_attachment" "app_runner_access_policy" {
  role       = aws_iam_role.app_runner_access_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# IAM Role for App Runner instance (to access SSM parameters)
resource "aws_iam_role" "app_runner_instance_role" {
  name = "${var.app_name}-app-runner-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "tasks.apprunner.amazonaws.com"
        }
      },
    ]
  })

  tags = {
    Name        = "${var.app_name}-instance-role"
    Application = var.app_name
  }
}

# Policy to allow App Runner to read SSM parameters
resource "aws_iam_role_policy" "app_runner_ssm_policy" {
  name = "${var.app_name}-ssm-access"
  role = aws_iam_role.app_runner_instance_role.id

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

resource "aws_apprunner_service" "this" {
  service_name = var.app_name

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.app_runner_access_role.arn
    }
    image_repository {
      image_configuration {
        port = "8501"

        # Non-sensitive configuration as environment variables
        runtime_environment_variables = {
          MODEL_PROVIDER = var.model_provider
          MODEL_NAME     = var.model_name
        }

        # Sensitive API keys from SSM Parameter Store
        runtime_environment_secrets = {
          OPENAI_API_KEY  = aws_ssm_parameter.openai_api_key.arn
          MISTRAL_API_KEY = aws_ssm_parameter.mistral_api_key.arn
        }
      }
      image_identifier      = var.image_identifier
      image_repository_type = var.image_repo_type
    }
    auto_deployments_enabled = false
  }

  instance_configuration {
    cpu               = "1024"
    memory            = "2048"
    instance_role_arn = aws_iam_role.app_runner_instance_role.arn
  }

  tags = {
    Name        = var.app_name
    Application = var.app_name
  }
}
