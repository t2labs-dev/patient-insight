# Dockerfile for Patient Insight Extractor - Lambda compatible
# Uses AWS Lambda Web Adapter to run Streamlit in Lambda

FROM public.ecr.aws/lambda/python:3.11

# Copy Lambda Web Adapter from public ECR
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

# Set environment variables for Lambda Web Adapter
ENV PORT=8501
ENV AWS_LWA_INVOKE_MODE=response_stream

# Set the working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Install system dependencies
RUN yum install -y \
    gcc \
    gcc-c++ \
    make \
    && yum clean all

# Install uv for fast dependency management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy project files
COPY pyproject.toml uv.lock ./
COPY *.py ./

# Install dependencies using uv
RUN uv sync --frozen

# Create startup script
RUN echo '#!/bin/sh' > /opt/bootstrap && \
    echo 'exec uv run streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true --server.runOnSave=false' >> /opt/bootstrap && \
    chmod +x /opt/bootstrap

# Lambda handler (not used with Web Adapter, but required)
CMD ["app.handler"]
