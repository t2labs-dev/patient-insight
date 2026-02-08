# GitHub Actions CI/CD Pipeline

This GitHub Actions workflow automates the build, test, and deployment process for the Patient Insight Extractor application.

## Pipeline Overview

The pipeline consists of two jobs:

1. **Build and Test**: Runs on every push and pull request
2. **Deploy**: Runs only on the main branch with manual approval

## Workflow Jobs

### 1. Build and Test Job

This job automatically runs on:
- Push to `main` branch
- Pull requests to `main` branch
- Manual workflow dispatch

**Steps:**
- Checks out the code
- Configures AWS credentials
- Logs into Amazon ECR
- Builds the Docker image
- Runs tests inside the container
- Pushes the image to ECR (only on main branch)

### 2. Deploy Job

This job:
- Requires manual approval (GitHub environment protection)
- Only runs on the main branch
- Depends on successful build and test job
- Updates the AWS App Runner service with the new image
- Waits for deployment to complete
- Provides the service URL

## Prerequisites

### 1. AWS Setup

#### Create an ECR Repository
```bash
aws ecr create-repository \
  --repository-name patient-insight-extractor \
  --region eu-west-3
```

#### Create an IAM OIDC Identity Provider for GitHub

Follow [AWS documentation](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html) or use:

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

#### Create an IAM Role for GitHub Actions

Create a trust policy file `trust-policy.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_GITHUB_USERNAME/YOUR_REPO_NAME:*"
        }
      }
    }
  ]
}
```

Create the role:
```bash
aws iam create-role \
  --role-name GitHubActionsRole \
  --assume-role-policy-document file://trust-policy.json
```

#### Attach Necessary Policies

```bash
# ECR permissions
aws iam attach-role-policy \
  --role-name GitHubActionsRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

# App Runner permissions
aws iam attach-role-policy \
  --role-name GitHubActionsRole \
  --policy-arn arn:aws:iam::aws:policy/AWSAppRunnerFullAccess
```

### 2. GitHub Setup

#### Repository Secrets

Add the following secret to your GitHub repository:
- Go to **Settings** → **Secrets and variables** → **Actions**
- Add **New repository secret**:
  - `AWS_ROLE_TO_ASSUME`: The ARN of the IAM role created above (e.g., `arn:aws:iam::123456789012:role/GitHubActionsRole`)

#### Environment Setup (for manual deployment)

1. Go to **Settings** → **Environments**
2. Create a new environment named `production`
3. Configure protection rules:
   - Check **Required reviewers** and add yourself or team members
   - This ensures manual approval before deployment

### 3. Deploy Infrastructure First

Before running the pipeline, deploy the Terraform infrastructure:

```bash
cd terraform

# Initialize Terraform
terraform init

# Create ECR repository and get the URI
export ECR_REPO=$(aws ecr describe-repositories \
  --repository-names patient-insight-extractor \
  --region eu-west-3 \
  --query 'repositories[0].repositoryUri' \
  --output text)

# Plan and apply
terraform plan \
  -var="image_identifier=${ECR_REPO}:latest" \
  -var="openai_api_key=${OPENAI_API_KEY}" \
  -var="model_provider=openai" \
  -var="model_name=gpt-4o"

terraform apply \
  -var="image_identifier=${ECR_REPO}:latest" \
  -var="openai_api_key=${OPENAI_API_KEY}" \
  -var="model_provider=openai" \
  -var="model_name=gpt-4o"
```

## Usage

### Automatic Build and Test

Every push to main or pull request will automatically:
1. Build the Docker image
2. Run tests
3. Push the image to ECR (main branch only)

### Manual Deployment

1. Navigate to **Actions** tab in your GitHub repository
2. Select the **CI/CD Pipeline** workflow
3. Click **Run workflow** button
4. After the build completes, the deploy job will wait for approval
5. Review and approve the deployment
6. The service will be updated with the new image

## Monitoring

After deployment:
- Check the **Actions** tab for workflow run details
- View the service URL in the deployment summary
- Monitor the App Runner service in the AWS console

## Troubleshooting

### Pipeline fails to authenticate with AWS
- Verify the `AWS_ROLE_TO_ASSUME` secret is correct
- Check the IAM role trust policy allows your repository
- Ensure the OIDC provider is configured correctly

### Tests fail
- Review test output in the Actions logs
- Run tests locally: `docker build -t test . && docker run --rm test uv run python test_mock.py`

### Deployment fails
- Ensure Terraform infrastructure is deployed
- Check App Runner service exists in AWS console
- Verify IAM role has necessary permissions

### Image not updating
- Check if the image was pushed to ECR successfully
- Verify the App Runner service configuration
- Try updating the service manually to test permissions
