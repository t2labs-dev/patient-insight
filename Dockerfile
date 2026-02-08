# Dockerfile for Patient Insight Extractor - Lambda compatible
# Uses AWS Lambda Web Adapter to run Streamlit in Lambda

FROM public.ecr.aws/lambda/python:3.12

# Copy Lambda Web Adapter from public ECR
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

# Set environment variables for Lambda Web Adapter
ENV PORT=8501
ENV AWS_LWA_INVOKE_MODE=response_stream

# Set the working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Install system dependencies for building packages
# Python 3.12 Lambda uses AL2023 which has dnf/microdnf
RUN dnf install -y \
    gcc \
    gcc-c++ \
    make \
    && dnf clean all

# Upgrade pip to get better binary wheel support
RUN pip install --upgrade pip setuptools wheel

# Copy project files
COPY requirements.txt ./
COPY *.py ./

# Install dependencies
# Pip will use prebuilt wheels when available
RUN pip install --no-cache-dir -r requirements.txt

# Create startup script
RUN echo '#!/bin/sh' > /opt/bootstrap && \
    echo 'exec streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true --server.runOnSave=false' >> /opt/bootstrap && \
    chmod +x /opt/bootstrap

# Lambda handler (not used with Web Adapter, but required)
CMD ["app.handler"]
