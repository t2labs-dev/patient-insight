provider "aws" {
  region = var.aws_region
}

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
}

resource "aws_iam_role_policy_attachment" "app_runner_access_policy" {
  role       = aws_iam_role.app_runner_access_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
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
        runtime_environment_variables = {
          OPENAI_API_KEY  = var.openai_api_key
          MISTRAL_API_KEY = var.mistral_api_key
          MODEL_PROVIDER  = var.model_provider
          MODEL_NAME      = var.model_name
        }
      }
      image_identifier      = var.image_identifier
      image_repository_type = var.image_repo_type
    }
    auto_deployments_enabled = false
  }

  instance_configuration {
    cpu    = "1024"
    memory = "2048"
  }

  tags = {
    Name = var.app_name
  }
}
