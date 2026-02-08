#!/usr/bin/env bash
# Bootstrap script for Terraform remote state backend.
# Run this ONCE with admin AWS credentials before using the CI/CD pipeline.
#
# Usage: ./terraform/bootstrap.sh

set -euo pipefail

BUCKET_NAME="patient-insight-tf-state-production"
export AWS_REGION="eu-west-3"
export AWS_PROFILE="t2labs"
ROLE_NAME="GitHubActionsRole"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "==> Creating S3 bucket for Terraform state..."
if aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
  echo "    Bucket $BUCKET_NAME already exists, skipping."
else
  aws s3api create-bucket \
    --bucket "$BUCKET_NAME" \
    --create-bucket-configuration LocationConstraint="$AWS_REGION"
  echo "    Bucket created."
fi

echo "==> Enabling versioning on S3 bucket..."
aws s3api put-bucket-versioning \
  --bucket "$BUCKET_NAME" \
  --versioning-configuration Status=Enabled

echo "==> Blocking public access on S3 bucket..."
aws s3api put-public-access-block \
  --bucket "$BUCKET_NAME" \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "==> Attaching Terraform state policy to $ROLE_NAME..."
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name TerraformStatePolicy \
  --policy-document "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [
    {
      \"Sid\": \"S3State\",
      \"Effect\": \"Allow\",
      \"Action\": [
        \"s3:GetObject\",
        \"s3:PutObject\",
        \"s3:DeleteObject\",
        \"s3:ListBucket\"
      ],
      \"Resource\": [
        \"arn:aws:s3:::${BUCKET_NAME}\",
        \"arn:aws:s3:::${BUCKET_NAME}/*\"
      ]
    },
    {
      \"Sid\": \"KMSForSSM\",
      \"Effect\": \"Allow\",
      \"Action\": [
        \"kms:Decrypt\",
        \"kms:GenerateDataKey\"
      ],
      \"Resource\": \"*\"
    }
  ]
}"

echo ""
echo "==> Bootstrap complete!"
echo "    S3 bucket:  $BUCKET_NAME"
echo "    Region:     $AWS_REGION"
echo ""
echo "Next steps:"
echo "  1. Clean up orphaned AWS resources from previous partial applies"
echo "  2. Commit and push terraform changes"
echo "  3. Run the Terraform workflow with 'apply'"
