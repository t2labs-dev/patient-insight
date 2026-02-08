output "api_gateway_url" {
  description = "The URL of the API Gateway endpoint"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "lambda_function_name" {
  description = "The name of the Lambda function"
  value       = aws_lambda_function.app.function_name
}

output "lambda_function_arn" {
  description = "The ARN of the Lambda function"
  value       = aws_lambda_function.app.arn
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

    3. Re-apply Terraform to inject the new API keys into Lambda:
       terraform apply -var="image_identifier=<ECR_URI>:latest"

    4. Access your application at:
       ${aws_apigatewayv2_stage.default.invoke_url}
  EOT
}
