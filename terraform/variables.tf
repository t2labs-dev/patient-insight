variable "aws_region" {
  description = "The AWS region to deploy to"
  type        = string
  default     = "eu-west-3"
}

variable "app_name" {
  description = "The name of the application"
  type        = string
  default     = "patient-insight"
}

variable "image_repo_type" {
  description = "The type of the image repository (ECR or ECR_PUBLIC)"
  type        = string
  default     = "ECR"
}

variable "image_identifier" {
  description = "The identifier of the image (e.g., ECR image URI)"
  type        = string
}

variable "model_provider" {
  description = "Model provider (openai, mistral, ollama)"
  type        = string
  default     = "openai"
}

variable "model_name" {
  description = "Model name (e.g., gpt-4o)"
  type        = string
  default     = "gpt-4o"
}
