# Terraform Infrastructure

This directory contains the Terraform configuration for deploying the Patient Insight Extractor to AWS App Runner.

## Architecture

The infrastructure consists of:

1. **AWS Systems Manager (SSM) Parameter Store**: Securely stores API keys
2. **IAM Roles**:
   - App Runner Access Role: Allows App Runner to pull images from ECR
   - App Runner Instance Role: Allows the running application to read SSM parameters
3. **AWS App Runner Service**: Hosts the containerized application

## Security Features

- **API Keys in SSM Parameter Store**: API keys are stored securely in AWS SSM instead of being passed through Terraform variables or GitHub secrets
- **Lifecycle Management**: SSM parameters use `lifecycle.ignore_changes` to prevent Terraform from overwriting manually set values
- **Least Privilege IAM**: The instance role only has permissions to read specific SSM parameters
- **Secure Transmission**: API keys are never exposed in logs, Terraform state (after initial placeholder), or CI/CD outputs

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.9.0
- An ECR repository (created automatically by the Terraform workflow)

## Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `aws_region` | AWS region to deploy to | `eu-west-3` | No |
| `app_name` | Application name | `patient-insight-extractor` | No |
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
  --name "/patient-insight-extractor/openai-api-key" \
  --value "sk-..." \
  --type SecureString \
  --overwrite \
  --region eu-west-3

# Set Mistral API Key (if using Mistral)
aws ssm put-parameter \
  --name "/patient-insight-extractor/mistral-api-key" \
  --value "..." \
  --type SecureString \
  --overwrite \
  --region eu-west-3
```

### Step 3: Restart App Runner

```bash
# Get the service ARN
SERVICE_ARN=$(terraform output -raw app_runner_service_arn)

# Restart to pick up new API keys
aws apprunner start-deployment \
  --service-arn $SERVICE_ARN \
  --region eu-west-3
```

## Outputs

After deployment, the following outputs are available:

- `app_runner_service_url`: The public URL of your application
- `app_runner_service_arn`: The ARN of the App Runner service
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
  --name "/patient-insight-extractor/openai-api-key" \
  --with-decryption \
  --region eu-west-3 \
  --query 'Parameter.Value' \
  --output text
```

### Updating Keys

```bash
# Update the parameter
aws ssm put-parameter \
  --name "/patient-insight-extractor/openai-api-key" \
  --value "new-key-value" \
  --type SecureString \
  --overwrite \
  --region eu-west-3

# Restart App Runner
aws apprunner start-deployment \
  --service-arn $(terraform output -raw app_runner_service_arn) \
  --region eu-west-3
```

### Deleting Keys (if needed)

```bash
aws ssm delete-parameter \
  --name "/patient-insight-extractor/openai-api-key" \
  --region eu-west-3
```

## Troubleshooting

### App Runner Service Fails to Start

Check CloudWatch Logs for the App Runner service to see specific error messages.

### Application Can't Read API Keys

Verify:
1. SSM parameters are set with correct values
2. Instance role has permissions to read the parameters
3. Parameter names match what the application expects

```bash
# Check if parameters exist
aws ssm describe-parameters \
  --filters "Key=Name,Values=/patient-insight-extractor/" \
  --region eu-west-3

# Verify IAM role permissions
aws iam get-role-policy \
  --role-name patient-insight-extractor-app-runner-instance-role \
  --policy-name patient-insight-extractor-ssm-access \
  --region eu-west-3
```

### Updating Infrastructure Without Affecting API Keys

The SSM parameters use `lifecycle.ignore_changes = [value]`, so running `terraform apply` won't overwrite your manually set API keys. However, if you destroy and recreate the infrastructure, you'll need to reset the API keys.

## Clean Up

To destroy all infrastructure:

```bash
terraform destroy \
  -var="image_identifier=<ECR_URI>:latest"
```

**Note**: This will delete the SSM parameters and all associated data. Make sure to backup any important configuration before destroying.

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use SSM Parameter Store** or AWS Secrets Manager for sensitive data
3. **Rotate API keys regularly** using the update commands above
4. **Monitor access** to SSM parameters using CloudTrail
5. **Use least privilege IAM policies** - only grant access to specific parameters

## Additional Resources

- [AWS App Runner Documentation](https://docs.aws.amazon.com/apprunner/)
- [AWS Systems Manager Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
