### Deployment Guide: Streamlit App on AWS

There are several ways to deploy this application to AWS. The most recommended and straightforward method for a Streamlit app is using **AWS App Runner**.

#### 1. Containerize the App (Recommended)

I've already created a `Dockerfile` for you. This allows you to package your app with all its dependencies.

#### 2. Option A: AWS App Runner (Easiest)

AWS App Runner is a fully managed service that makes it easy to deploy containerized web applications.

1.  **Push Code to GitHub**: Push your project (including the `Dockerfile`) to a GitHub repository.
2.  **Create Service in App Runner**:
    *   Go to the [AWS App Runner Console](https://console.aws.amazon.com/apprunner/).
    *   Click **Create App Runner service**.
    *   **Source**: Select "Source code repository" and connect your GitHub account.
    *   **Deployment Settings**: Choose "Automatic" (every push to main will redeploy).
    *   **Configuration**: Choose "Configure all settings here".
        *   **Runtime**: Python 3.
        *   **Build command**: `pip install uv && uv sync` (Note: AWS might prefer standard pip, but our Dockerfile handles it better).
        *   **Start command**: `uv run streamlit run app.py --server.port 8080`
        *   **Port**: 8080 (or 8501, just match the start command).
    *   **Environment Variables**: Add your `OPENAI_API_KEY` or `MISTRAL_API_KEY` here.
3.  **Review and Create**: AWS will build and deploy your app. You'll get a URL (e.g., `xxx.aws-apprunner.com`) to access it.

#### 3. Option B: AWS Elastic Beanstalk (Traditional)

1.  Initialize EB CLI: `eb init`.
2.  Create environment: `eb create patient-insights-env`.
3.  Set environment variables: `eb setenv OPENAI_API_KEY=your_key`.

#### 4. Option C: Amazon EC2 (Manual)

1.  Launch a Linux EC2 instance (e.g., t3.medium).
2.  Install Docker and Git.
3.  Clone your repo.
4.  Build and run:
    ```bash
    docker build -t patient-app .
    docker run -p 80:8501 --env-file .env patient-app
    ```
5.  Open port 80 in your Security Group.

### Important Notes
- **Local Models**: If you use Ollama, you cannot easily run it inside App Runner unless you also containerize Ollama and run it in the same network or use an EC2 instance with more resources.
- **Security**: Never commit your `.env` file to GitHub. Use AWS Secrets Manager or App Runner Environment Variables to store keys.

### 4. Automated Deployment with Terraform (Infrastructure as Code)

If you prefer to deploy using Infrastructure as Code, we have provided a Terraform configuration in the `terraform/` directory. This will set up the AWS App Runner service and necessary IAM roles.

#### Prerequisites:
- [Terraform](https://www.terraform.io/downloads.html) installed.
- AWS CLI configured with appropriate permissions.
- Your Docker image already pushed to Amazon ECR.

#### Steps:
1. Navigate to the terraform directory:
   ```bash
   cd terraform
   ```
2. Initialize Terraform:
   ```bash
   terraform init
   ```
3. Create a `terraform.tfvars` file to provide your specific values:
   ```hcl
   image_identifier = "YOUR_ACCOUNT_ID.dkr.ecr.eu-west-3.amazonaws.com/patient-insight-extractor:latest"
   openai_api_key   = "your-key"
   # or mistral_api_key = "your-key"
   ```
4. Plan and apply:
   ```bash
   terraform plan
   terraform apply
   ```
5. Once complete, Terraform will output the `app_runner_service_url`.
