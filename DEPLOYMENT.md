# Deployment Guide - AWS Lambda + API Gateway

This document provides a complete guide for deploying the Patient Insight Extractor application using AWS Lambda and API Gateway.

## Architecture Overview

```
┌─────────┐      ┌──────────────┐      ┌────────┐      ┌──────────┐
│  User   │─────>│ API Gateway  │─────>│ Lambda │─────>│ Streamlit│
└─────────┘      │  (HTTP API)  │      │  +LWA  │      │   App    │
                 └──────────────┘      └────────┘      └──────────┘

                                       ┌─────────┐
                                       │   SSM   │
                                       │Parameter│ (read by Terraform)
                                       │  Store  │
                                       └─────────┘
```

**Components:**
- **API Gateway**: Public HTTP endpoint that routes requests to Lambda
- **Lambda**: Runs the containerized Streamlit application using Lambda Web Adapter
- **SSM Parameter Store**: Securely stores API keys (Terraform reads and injects into Lambda as env vars)
- **ECR**: Stores the Docker container image
- **CloudWatch**: Logs for debugging and monitoring

## Why Lambda + API Gateway?

**Cost Savings:**
- **App Runner**: ~$15-30/month (always running)
- **Lambda**: ~$0-5/month (pay per use)
- **Free Tier**: First 1M requests/month free

**Other Benefits:**
- Automatic scaling (0 to thousands of requests)
- No idle costs when not in use
- Built-in monitoring and logging
- Easy to update and rollback

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **GitHub Account** with repository access
3. **OpenAI API Key** (or Mistral API key)
4. **AWS CLI** installed and configured
5. **Terraform** installed (optional, for local deployment)

## Quick Start

### 1. Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add the following secrets:
- `AWS_ROLE_TO_ASSUME`: IAM role ARN for GitHub Actions (e.g., `arn:aws:iam::123456789012:role/GitHubActionsRole`)
- `MODEL_PROVIDER`: (optional) `openai` or `mistral` (default: `openai`)
- `MODEL_NAME`: (optional) Model to use (default: `gpt-4o`)

### 2. Create GitHub Environments

Go to Settings → Environments

Create two environments:
1. **production**: For application deployments
   - Add required reviewers (yourself or team members)
2. **terraform-production**: For infrastructure changes
   - Add required reviewers (yourself or team members)

### 3. Deploy Infrastructure

**Option A: Using GitHub Actions (Recommended)**

1. Go to Actions → Terraform Infrastructure
2. Click "Run workflow"
3. Select `plan` to review changes
4. Review the plan output
5. Run workflow again with `apply`
6. Approve the deployment when prompted

**Option B: Using Terraform CLI**

```bash
cd terraform

# Initialize
terraform init

# Plan
terraform plan \
  -var="image_identifier=<ECR_URI>:latest" \
  -out=tfplan

# Apply
terraform apply tfplan
```

### 4. Set API Keys in AWS

After infrastructure deployment, set your API keys and re-apply Terraform:

```bash
# Get parameter names
terraform output ssm_openai_api_key_parameter
terraform output ssm_mistral_api_key_parameter

# Set OpenAI key
aws ssm put-parameter \
  --name "/patient-insight/openai-api-key" \
  --value "sk-your-actual-key-here" \
  --type SecureString \
  --overwrite \
  --region eu-west-3

# Set Mistral key (if using Mistral)
aws ssm put-parameter \
  --name "/patient-insight/mistral-api-key" \
  --value "your-actual-key-here" \
  --type SecureString \
  --overwrite \
  --region eu-west-3

# Re-apply Terraform to inject API keys into Lambda environment variables
cd terraform
terraform apply -var="image_identifier=<ECR_URI>:latest"
```

### 5. Deploy Application

**Option A: Using GitHub Actions (Recommended)**

1. Push code to main branch or create a PR
2. Wait for build and test to complete
3. Go to Actions → CI/CD Pipeline
4. The deploy job will wait for approval
5. Approve the deployment
6. Access your application at the API Gateway URL

**Option B: Manual Deployment**

```bash
# Build and push Docker image
docker build -t patient-insight .
docker tag patient-insight:latest <ECR_URI>:latest
docker push <ECR_URI>:latest

# Update Lambda function
aws lambda update-function-code \
  --function-name patient-insight \
  --image-uri <ECR_URI>:latest \
  --region eu-west-3

# Wait for update
aws lambda wait function-updated-v2 \
  --function-name patient-insight \
  --region eu-west-3
```

### 6. Access Your Application

Get the API Gateway URL:
```bash
terraform output api_gateway_url
```

Or from AWS CLI:
```bash
aws apigatewayv2 get-apis \
  --query "Items[?Name=='patient-insight-api'].ApiEndpoint" \
  --output text \
  --region eu-west-3
```

Open the URL in your browser!

## Updating the Application

### Update Code

1. Make changes to your code
2. Commit and push to main branch
3. GitHub Actions will automatically:
   - Build new Docker image
   - Run tests
   - Push to ECR
   - Wait for your approval
   - Update Lambda function

### Update API Keys

```bash
# Update the key in SSM
aws ssm put-parameter \
  --name "/patient-insight/openai-api-key" \
  --value "new-key-here" \
  --type SecureString \
  --overwrite \
  --region eu-west-3

# Re-apply Terraform to update Lambda environment variables
cd terraform
terraform apply -var="image_identifier=<ECR_URI>:latest"
```

### Update Infrastructure

1. Modify Terraform files in `terraform/` directory
2. Commit and push to main branch
3. GitHub Actions will automatically create a plan
4. Review the plan in the workflow output
5. Go to Actions → Terraform Infrastructure → Run workflow → Select `apply`
6. Approve the changes when prompted

## Monitoring and Debugging

### View Lambda Logs

```bash
# Tail logs in real-time
aws logs tail /aws/lambda/patient-insight --follow --region eu-west-3

# View recent logs
aws logs tail /aws/lambda/patient-insight --since 1h --region eu-west-3
```

### View API Gateway Logs

```bash
aws logs tail /aws/apigateway/patient-insight --follow --region eu-west-3
```

### Monitor Lambda Performance

Go to AWS Console → Lambda → patient-insight → Monitor

View metrics:
- Invocations
- Duration
- Error count
- Throttles
- Concurrent executions

### Check Lambda Function Status

```bash
aws lambda get-function \
  --function-name patient-insight \
  --region eu-west-3
```

## Troubleshooting

### Application Not Loading

**Check Lambda Logs:**
```bash
aws logs tail /aws/lambda/patient-insight --since 10m --region eu-west-3
```

**Common Issues:**
- Lambda timeout (increase timeout in `terraform/main.tf`)
- Memory limit (increase memory_size in `terraform/main.tf`)
- SSM parameter not set (check with `aws ssm get-parameter`)
- Docker image not compatible with Lambda

### API Gateway 502 Errors

This usually means Lambda is having issues:
1. Check Lambda logs for errors
2. Verify Streamlit is starting correctly
3. Test Lambda directly:
```bash
aws lambda invoke \
  --function-name patient-insight \
  --payload '{}' \
  --region eu-west-3 \
  response.json
```

### SSM Parameter Errors

**Verify parameter exists:**
```bash
aws ssm get-parameter \
  --name "/patient-insight/openai-api-key" \
  --with-decryption \
  --region eu-west-3
```

**Check Lambda environment variables:**
```bash
aws lambda get-function-configuration \
  --function-name patient-insight \
  --region eu-west-3 \
  --query 'Environment.Variables'
```

### Slow Performance

**Increase Lambda resources:**
Edit `terraform/main.tf`:
```hcl
resource "aws_lambda_function" "app" {
  memory_size = 3008  # Increase from 2048
  timeout     = 600   # Increase from 300
  ...
}
```

**Enable provisioned concurrency** (eliminates cold starts):
```hcl
resource "aws_lambda_provisioned_concurrency_config" "app" {
  function_name                     = aws_lambda_function.app.function_name
  provisioned_concurrent_executions = 1
  qualifier                         = aws_lambda_function.app.version
}
```

## Cost Optimization

### Lambda Pricing

- **Requests**: $0.20 per 1M requests (first 1M free)
- **Duration**: $0.0000166667 per GB-second (400,000 GB-seconds free)
- **Example**: 10,000 requests/month with 5-second avg duration and 2 GB memory
  - Requests: $0 (within free tier)
  - Duration: $0.83
  - **Total: ~$0.83/month**

### API Gateway Pricing

- **HTTP API**: $1.00 per million requests (first 1M free)
- **Example**: 10,000 requests/month
  - **Total: $0 (within free tier)**

### ECR Pricing

- **Storage**: $0.10 per GB/month
- **Typical image size**: 500 MB - 1 GB
- **Total: ~$0.05-0.10/month**

### Total Estimated Cost

For low to medium traffic (~10,000 requests/month):
- **$0-5/month** (mostly covered by free tier)

Compare to App Runner:
- **$15-30/month minimum** (always running)

## Best Practices

### Security

1. **Rotate API keys regularly**
2. **Use SSM Parameter Store** for all secrets
3. **Enable AWS WAF** for production (optional)
4. **Monitor CloudTrail** for SSM parameter access
5. **Use least privilege IAM** policies

### Performance

1. **Monitor CloudWatch metrics** regularly
2. **Adjust memory/timeout** based on actual usage
3. **Consider provisioned concurrency** for production
4. **Optimize Docker image** size

### Cost

1. **Review AWS Cost Explorer** monthly
2. **Set up billing alerts**
3. **Clean up unused resources**
4. **Use AWS Budgets** to track spending

### Reliability

1. **Set up CloudWatch alarms** for errors
2. **Enable X-Ray tracing** for debugging
3. **Use multiple availability zones** (automatic with Lambda)
4. **Implement proper error handling** in code

## Cleanup

To completely remove all infrastructure:

```bash
cd terraform
terraform destroy -var="image_identifier=<ECR_URI>:latest"
```

**Warning**: This will delete:
- Lambda function
- API Gateway
- SSM parameters
- CloudWatch log groups
- IAM roles

Make sure to backup any important data first!

## Additional Resources

- [Terraform README](terraform/README.md) - Detailed infrastructure documentation
- [GitHub Workflows README](.github/workflows/README.md) - CI/CD pipeline documentation
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS Lambda Web Adapter](https://github.com/awslabs/aws-lambda-web-adapter)
- [Streamlit Documentation](https://docs.streamlit.io/)

## Support

For issues or questions:
1. Check CloudWatch logs first
2. Review the troubleshooting section above
3. Check GitHub Actions workflow logs
4. Open an issue in the GitHub repository
