output "app_runner_service_url" {
  description = "The URL of the App Runner service"
  value       = aws_apprunner_service.this.service_url
}

output "app_runner_service_arn" {
  description = "The ARN of the App Runner service"
  value       = aws_apprunner_service.this.arn
}
