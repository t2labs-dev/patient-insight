"""
Secret Resolution Utility for AWS Lambda and Local Development

This module provides automatic secret resolution that works in both:
- Production (AWS Lambda): Retrieves secrets from AWS SSM Parameter Store
- Local Development: Uses raw values from .env file

Contract:
- If an environment variable value starts with '/', it's an SSM parameter name
- Otherwise, it's a raw secret value (local development)
"""

import os
import logging
from typing import Optional, Dict

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Global cache for resolved secrets
_secrets_cache: Dict[str, str] = {}


class SecretResolutionError(Exception):
    """Raised when secret resolution fails"""
    pass


def _is_ssm_parameter_name(value: str) -> bool:
    """Check if the value is an SSM parameter name (starts with /)"""
    return value.startswith("/")


def _get_from_ssm(parameter_name: str) -> str:
    """
    Retrieve a secret from AWS Systems Manager Parameter Store

    Args:
        parameter_name: SSM parameter name (e.g., /myapp/openai/api_key)

    Returns:
        The decrypted parameter value

    Raises:
        SecretResolutionError: If retrieval fails
    """
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError

        ssm = boto3.client('ssm')

        logger.info(f"Retrieving parameter from SSM (name hidden for security)")

        response = ssm.get_parameter(
            Name=parameter_name,
            WithDecryption=True
        )

        return response['Parameter']['Value']

    except ImportError:
        raise SecretResolutionError(
            "boto3 is required to retrieve secrets from AWS SSM. "
            "Install it with: pip install boto3"
        )
    except NoCredentialsError:
        raise SecretResolutionError(
            "AWS credentials not found. Ensure your Lambda has proper IAM permissions "
            "or configure AWS credentials for local testing."
        )
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == 'ParameterNotFound':
            raise SecretResolutionError(
                f"SSM parameter not found: {parameter_name}"
            )
        elif error_code == 'AccessDeniedException':
            raise SecretResolutionError(
                f"Access denied to SSM parameter: {parameter_name}. "
                "Check IAM permissions (ssm:GetParameter)."
            )
        else:
            raise SecretResolutionError(
                f"Failed to retrieve SSM parameter: {error_code} - {str(e)}"
            )
    except Exception as e:
        raise SecretResolutionError(
            f"Unexpected error retrieving SSM parameter: {str(e)}"
        )


def get_secret(env_var_name: str, required: bool = True) -> Optional[str]:
    """
    Retrieve a secret from environment variable, automatically resolving SSM parameters

    This function:
    1. Reads the environment variable
    2. Determines if it's an SSM parameter name (starts with '/') or a raw value
    3. Retrieves from SSM if needed, or returns the raw value
    4. Caches the result to avoid repeated SSM calls
    5. Never logs or exposes the actual secret value

    Args:
        env_var_name: Name of the environment variable to read
        required: If True, raises an error if the secret is not found

    Returns:
        The resolved secret value, or None if not required and not found

    Raises:
        SecretResolutionError: If secret resolution fails and required=True

    Examples:
        # Production (AWS Lambda):
        # Environment: OPENAI_API_KEY=/myapp/openai/api_key
        api_key = get_secret("OPENAI_API_KEY")  # Retrieves from SSM

        # Local development:
        # Environment: OPENAI_API_KEY=sk-proj-xxx
        api_key = get_secret("OPENAI_API_KEY")  # Returns raw value
    """
    # Check cache first
    if env_var_name in _secrets_cache:
        logger.debug(f"Using cached secret for {env_var_name}")
        return _secrets_cache[env_var_name]

    # Read environment variable
    env_value = os.getenv(env_var_name)

    if env_value is None:
        if required:
            raise SecretResolutionError(
                f"Required environment variable '{env_var_name}' is not set"
            )
        logger.debug(f"Optional secret '{env_var_name}' not found")
        return None

    # Determine if it's an SSM parameter name or raw value
    if _is_ssm_parameter_name(env_value):
        logger.info(f"Resolving {env_var_name} from SSM Parameter Store")
        try:
            secret_value = _get_from_ssm(env_value)
            _secrets_cache[env_var_name] = secret_value
            logger.info(f"Successfully resolved {env_var_name} from SSM")
            return secret_value
        except SecretResolutionError as e:
            if required:
                raise
            logger.warning(f"Failed to resolve optional secret {env_var_name}: {e}")
            return None
    else:
        # Raw value (local development)
        logger.debug(f"Using raw value for {env_var_name} (local development mode)")
        _secrets_cache[env_var_name] = env_value
        return env_value


def clear_cache():
    """Clear the secrets cache. Useful for testing."""
    global _secrets_cache
    _secrets_cache = {}
    logger.debug("Secrets cache cleared")


# Convenience functions for common secret types

def get_openai_api_key() -> str:
    """Get OpenAI API key from OPENAI_API_KEY environment variable"""
    return get_secret("OPENAI_API_KEY", required=True)


def get_mistral_api_key() -> str:
    """Get Mistral API key from MISTRAL_API_KEY environment variable"""
    return get_secret("MISTRAL_API_KEY", required=True)