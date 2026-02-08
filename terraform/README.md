# Terraform Infrastructure - Lambda + API Gateway

This directory contains the Terraform configuration for deploying the Patient Insight Extractor to AWS Lambda with API Gateway.

## Architecture

The infrastructure consists of:

1. **AWS Lambda Function**: Runs the containerized Streamlit application
   - Uses AWS Lambda Web Adapter to run Streamlit in Lambda
   - Container image pulled from Amazon ECR
   - 2048 MB memory, 300 second timeout
   - Configured with environment variables for model provider/name and API keys

2. **AWS API Gateway (HTTP API)**: Provides public HTTP endpoint
   - Routes all requests to the Lambda function
   - CORS enabled for web access
   - CloudWatch logging enabled

3. **AWS Systems Manager (SSM) Parameter Store**: Securely stores API keys
   - Encrypted with AWS KMS
   - Separate parameters for OpenAI and Mistral keys
   - Managed manually (not through Terraform)

4. **IAM Roles**:
   - Lambda Execution Role: Allows Lambda to write logs to CloudWatch

5. **CloudWatch Log Groups**: For Lambda and API Gateway logs
   - 7-day retention period
   - Structured logging for debugging

## Cost Optimization

This architecture using Lambda + API Gateway is significantly cheaper than App Runner:

- **Pay-per-use**: Only charged when the application is accessed
- **No idle costs**: No charges when not in use
- **Free tier**: Lambda and API Gateway both have generous free tiers
- **Estimated monthly cost**: $0-5 for low to medium traffic (vs $15-30+ for App Runner)

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.9.0
- An ECR repository (created automatically by the Terraform workflow)
- Docker image built with Lambda Web Adapter support

## Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `aws_region` | AWS region to deploy to | `eu-west-3` | No |
| `app_name` | Application name | `patient-insight` | No |
| `image_identifier` | ECR image URI | - | Yes |
| `image_repo_type` | Repository type (ECR/ECR_PUBLIC) | `ECR` | No |
| `model_provider` | LLM provider | `openai` | No |
| `model_name` | LLM model name | `gpt-4o` | No |

## Deployment

### Option 1: GitHub Actions (Recommended)

See `.github/workflows/README.md` for details on using the automated workflow.

### Option 2: Local Deployment

```bash
# Initialize Terraform
terraform init

# Create a plan
terraform plan \
  -var="image_identifier=<ECR_URI>:latest" \
  -var="model_provider=openai" \
  -var="model_name=gpt-4o" \
  -out=tfplan

# Apply the plan
terraform apply tfplan
```

## Post-Deployment: Configure API Keys

After deploying the infrastructure, you must set your API keys in AWS SSM Parameter Store:

### Step 1: Get Parameter Names

```bash
terraform output ssm_openai_api_key_parameter
terraform output ssm_mistral_api_key_parameter
```

### Step 2: Set API Keys

```bash
# Set OpenAI API Key
aws ssm put-parameter \
  --name "/patient-insight/openai-api-key" \
  --value "sk-..." \
  --type SecureString \
  --overwrite \
  --region eu-west-3

# Set Mistral API Key (if using Mistral)
aws ssm put-parameter \
  --name "/patient-insight/mistral-api-key" \
  --value "..." \
  --type SecureString \
  --overwrite \
  --region eu-west-3
```

### Step 3: Update Lambda Function

After updating SSM parameters, you need to redeploy with Terraform to inject the new values:

```bash
# Terraform will read the updated SSM parameters and update Lambda
terraform apply -var="image_identifier=<ECR_URI>:latest"
```

Or trigger a redeployment via GitHub Actions.

## How It Works

### Lambda Web Adapter

The application uses [AWS Lambda Web Adapter](https://github.com/awslabs/aws-lambda-web-adapter) to run Streamlit in Lambda:

1. Lambda Web Adapter starts as a Lambda extension
2. It launches the Streamlit server on port 8501
3. It proxies HTTP requests from API Gateway to Streamlit
4. Streamlit responds as if running on a normal server

### SSM Parameter Integration

API keys are stored securely in SSM Parameter Store and injected into Lambda:

1. API keys are stored in SSM Parameter Store (encrypted with KMS)
2. Terraform reads the SSM parameters using data sources
3. Values are injected as environment variables into Lambda
4. Application reads them from standard environment variables
5. Locally, use `.env` files for development

### Request Flow

```
User → API Gateway → Lambda (Web Adapter) → Streamlit App → LLM API
```

## Outputs

After deployment, the following outputs are available:

- `api_gateway_url`: The public URL of your application
- `lambda_function_name`: The name of the Lambda function
- `lambda_function_arn`: The ARN of the Lambda function
- `ssm_openai_api_key_parameter`: SSM parameter name for OpenAI API key
- `ssm_mistral_api_key_parameter`: SSM parameter name for Mistral API key
- `instructions`: Detailed post-deployment instructions

View all outputs:
```bash
terraform output
```

## Managing API Keys

### Viewing Current Keys (Decrypted)

```bash
aws ssm get-parameter \
  --name "/patient-insight/openai-api-key" \
  --with-decryption \
  --region eu-west-3 \
  --query 'Parameter.Value' \
  --output text
```

### Updating Keys

```bash
# Update the parameter
aws ssm put-parameter \
  --name "/patient-insight/openai-api-key" \
  --value "new-key-value" \
  --type SecureString \
  --overwrite \
  --region eu-west-3

# Redeploy Lambda to pick up new values
cd terraform
terraform apply -var="image_identifier=<ECR_URI>:latest"
```

### Deleting Keys (if needed)

```bash
aws ssm delete-parameter \
  --name "/patient-insight/openai-api-key" \
  --region eu-west-3
```

## Troubleshooting

### Lambda Function Fails to Start

Check CloudWatch Logs for the Lambda function:
```bash
aws logs tail /aws/lambda/patient-insight --follow --region eu-west-3
```

### Application Can't Read API Keys

Verify:
1. SSM parameters are set with correct values
2. Terraform has been applied after setting SSM parameters
3. Lambda environment variables contain the keys

```bash
# Check if parameters exist
aws ssm describe-parameters \
  --filters "Key=Name,Values=/patient-insight/" \
  --region eu-west-3

# Check Lambda environment variables
aws lambda get-function-configuration \
  --function-name patient-insight \
  --region eu-west-3 \
  --query 'Environment.Variables'
```

### Lambda Timeout

If the application is slow to start or process requests:
- Increase `timeout` in `main.tf` (default: 300 seconds)
- Increase `memory_size` for better performance (default: 2048 MB)
- Consider using provisioned concurrency for faster cold starts

### API Gateway 502 Errors

This usually means Lambda is returning an invalid response:
- Check Lambda logs for errors
- Ensure Streamlit is starting correctly
- Verify Lambda Web Adapter is configured properly

## Performance Tuning

### Cold Start Optimization

Lambda cold starts can be slow for container images. To optimize:

1. **Use smaller base images**: The Dockerfile uses `public.ecr.aws/lambda/python:3.11` which is optimized for Lambda
2. **Minimize dependencies**: Only install required packages
3. **Use provisioned concurrency**: For production, consider enabling provisioned concurrency

```hcl
resource "aws_lambda_provisioned_concurrency_config" "app" {
  function_name                     = aws_lambda_function.app.function_name
  provisioned_concurrent_executions = 1
  qualifier                         = aws_lambda_function.app.version
}
```

### Memory and Timeout

Adjust based on your application's needs:
- More memory = faster CPU and better performance
- Longer timeout = handles complex requests but costs more
- Monitor CloudWatch metrics to find optimal settings

## Clean Up

To destroy all infrastructure:

```bash
terraform destroy \
  -var="image_identifier=<ECR_URI>:latest"
```

**Note**: This will delete the SSM parameters and all associated data. Make sure to backup any important configuration before destroying.

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use SSM Parameter Store** with encryption for sensitive data
3. **Rotate API keys regularly** using the update commands above
4. **Monitor access** to SSM parameters using CloudTrail
5. **Use least privilege IAM policies** - only grant access to specific parameters
6. **Enable API Gateway throttling** to prevent abuse
7. **Use AWS WAF** (optional) for additional protection

## Additional Resources

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS Lambda Web Adapter](https://github.com/awslabs/aws-lambda-web-adapter)
- [AWS API Gateway HTTP APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html)
- [AWS Systems Manager Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
