# GitHub Actions CI/CD Pipelines

This repository contains two GitHub Actions workflows:

1. **CI/CD Pipeline** (`ci-cd.yml`): Automates the build, test, and application deployment
2. **Terraform Infrastructure** (`terraform.yml`): Manages infrastructure as code

## Workflows Overview

### CI/CD Pipeline (`ci-cd.yml`)

This pipeline consists of two jobs:

1. **Build and Test**: Runs on every push and pull request
2. **Deploy**: Runs only on the main branch with manual approval

### Terraform Infrastructure Pipeline (`terraform.yml`)

This pipeline consists of two jobs:

1. **Terraform Plan**: Automatically runs on every push/PR that modifies Terraform files
2. **Terraform Apply**: Manually triggered to apply infrastructure changes

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

## Terraform Infrastructure Workflow

### 1. Terraform Plan Job

This job **automatically** runs when:
- Push to `main` branch with changes to `terraform/` directory
- Pull requests to `main` branch with changes to `terraform/` directory
- Manual workflow dispatch

**Steps:**
- Checks out the code
- Configures AWS credentials
- Sets up Terraform
- Creates/verifies ECR repository exists
- Runs `terraform init`
- Runs `terraform fmt -check`
- Runs `terraform validate`
- Runs `terraform plan` and saves the plan
- Comments the plan on pull requests
- Uploads the plan as an artifact (valid for 5 days)

### 2. Terraform Apply Job

This job **only runs manually**:
- Triggered via workflow_dispatch with action='apply'
- Requires manual approval (GitHub environment protection: `terraform-production`)
- Downloads the saved plan from the Plan job
- Applies the infrastructure changes
- Outputs the App Runner service URL

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

Add the following secrets to your GitHub repository:
- Go to **Settings** → **Secrets and variables** → **Actions**
- Add **New repository secrets**:
  - `AWS_ROLE_TO_ASSUME`: The ARN of the IAM role created above (e.g., `arn:aws:iam::123456789012:role/GitHubActionsRole`)
  - `OPENAI_API_KEY`: Your OpenAI API key (required for Terraform)
  - `MISTRAL_API_KEY`: Your Mistral API key (optional, if using Mistral)
  - `MODEL_PROVIDER`: Model provider to use (optional, defaults to `openai`)
  - `MODEL_NAME`: Model name to use (optional, defaults to `gpt-4o`)

#### Environment Setup (for manual deployment)

1. Go to **Settings** → **Environments**
2. Create two environments:

   **Environment 1: `production`** (for application deployment)
   - Configure protection rules:
     - Check **Required reviewers** and add yourself or team members
     - This ensures manual approval before deploying the application

   **Environment 2: `terraform-production`** (for infrastructure changes)
   - Configure protection rules:
     - Check **Required reviewers** and add yourself or team members
     - This ensures manual approval before applying infrastructure changes

### 3. Deploy Infrastructure

You can deploy the infrastructure using either GitHub Actions (recommended) or locally.

#### Option A: Using GitHub Actions (Recommended)

1. Push your code to GitHub (including the `terraform/` directory)
2. The Terraform Plan workflow will run automatically
3. Review the plan in the Actions tab
4. Manually trigger the Terraform Apply workflow:
   - Go to **Actions** → **Terraform Infrastructure**
   - Click **Run workflow** → Select `apply`
   - Approve when prompted

#### Option B: Local Deployment

If you prefer to deploy locally:

```bash
cd terraform

# Initialize Terraform
terraform init

# The workflow will create the ECR repo automatically, but if needed:
export ECR_REPO=$(aws ecr describe-repositories \
  --repository-names patient-insight-extractor \
  --region eu-west-3 \
  --query 'repositories[0].repositoryUri' \
  --output text 2>/dev/null || \
  aws ecr create-repository \
  --repository-name patient-insight-extractor \
  --region eu-west-3 \
  --query 'repository.repositoryUri' \
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

### Deploying Infrastructure with Terraform

**Step 1: Automatic Plan**

When you modify files in the `terraform/` directory and push to main or create a PR:
1. The Terraform Plan job runs automatically
2. Review the plan output in the workflow summary
3. For PRs, the plan is commented on the pull request

**Step 2: Manual Apply**

To apply the infrastructure changes:
1. Navigate to **Actions** tab in your GitHub repository
2. Select the **Terraform Infrastructure** workflow
3. Click **Run workflow** button
4. Select `apply` from the dropdown
5. Click **Run workflow**
6. Wait for approval request (from the `terraform-production` environment)
7. Review and approve the infrastructure changes
8. The infrastructure will be created/updated
9. The App Runner service URL will be displayed in the summary

### Deploying the Application

**Step 1: Automatic Build and Test**

Every push to main or pull request will automatically:
1. Build the Docker image
2. Run tests
3. Push the image to ECR (main branch only)

**Step 2: Manual Deployment**

To deploy the application to App Runner:
1. Navigate to **Actions** tab in your GitHub repository
2. Select the **CI/CD Pipeline** workflow
3. Click **Run workflow** button
4. After the build completes, the deploy job will wait for approval
5. Review and approve the deployment (from the `production` environment)
6. The service will be updated with the new image

### Recommended Workflow

1. **First time setup**: Run Terraform Apply to create infrastructure
2. **Application updates**: Push code changes, then approve deployment
3. **Infrastructure updates**: Modify `terraform/` files, review plan, then run apply

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

### Terraform Plan fails
- Check that all required secrets are set (`OPENAI_API_KEY`, etc.)
- Verify AWS credentials have necessary permissions
- Review the error in the Actions logs
- Run `terraform validate` locally to check configuration

### Terraform Apply fails
- Ensure the plan artifact is available (not expired after 5 days)
- Check AWS quotas and limits for App Runner
- Verify the ECR repository exists
- Review Terraform state for conflicts

### Tests fail
- Review test output in the Actions logs
- Run tests locally: `docker build -t test . && docker run --rm test uv run python test_mock.py`

### Application deployment fails
- Ensure Terraform infrastructure is deployed first
- Check App Runner service exists in AWS console
- Verify IAM role has necessary permissions
- Check that the ECR image was pushed successfully

### Image not updating
- Check if the image was pushed to ECR successfully
- Verify the App Runner service configuration
- Try updating the service manually to test permissions
- Check if auto-deployments are disabled in App Runner

### Missing API keys or environment variables
- Verify all secrets are configured in GitHub repository settings
- Check that environment variables are correctly set in `terraform/variables.tf`
- Ensure secrets are referenced correctly in the workflow files
