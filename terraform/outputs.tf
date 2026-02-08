output "app_runner_service_url" {
  description = "The URL of the App Runner service"
  value       = aws_apprunner_service.this.service_url
}

output "app_runner_service_arn" {
  description = "The ARN of the App Runner service"
  value       = aws_apprunner_service.this.arn
}

output "ssm_openai_api_key_parameter" {
  description = "SSM Parameter name for OpenAI API Key (set this manually in AWS Console)"
  value       = aws_ssm_parameter.openai_api_key.name
}

output "ssm_mistral_api_key_parameter" {
  description = "SSM Parameter name for Mistral API Key (set this manually in AWS Console)"
  value       = aws_ssm_parameter.mistral_api_key.name
}

output "instructions" {
  description = "Next steps after deployment"
  value       = <<-EOT
    Deployment successful! Next steps:

    1. Set your API keys in AWS Systems Manager Parameter Store:
       - OpenAI API Key:  ${aws_ssm_parameter.openai_api_key.name}
       - Mistral API Key: ${aws_ssm_parameter.mistral_api_key.name}

    2. Update the parameters using AWS CLI:
       aws ssm put-parameter --name "${aws_ssm_parameter.openai_api_key.name}" --value "your-openai-key-here" --type SecureString --overwrite --region ${var.aws_region}
       aws ssm put-parameter --name "${aws_ssm_parameter.mistral_api_key.name}" --value "your-mistral-key-here" --type SecureString --overwrite --region ${var.aws_region}

    3. Restart the App Runner service to pick up the new values:
       aws apprunner start-deployment --service-arn ${aws_apprunner_service.this.arn} --region ${var.aws_region}

    4. Access your application at:
       https://${aws_apprunner_service.this.service_url}
  EOT
}
