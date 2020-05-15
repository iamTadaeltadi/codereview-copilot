import os
from dotenv import load_dotenv

# Load .env file with override for dev/staging flexibility
load_dotenv(override=True)

class Config:
    # Read variables with defaults if not found
    HYPERBOLIC = {
        "api_key": os.getenv("HYPERBOLIC_API_KEY"),
        "api_base_url": os.getenv("HYPERBOLIC_API_BASE_URL"),
    }
    CEREBRAS = {
        "api_key": os.getenv("CEREBRAS_API_KEY"),
        "api_base_url": os.getenv("CEREBRAS_API_BASE_URL"),
    }
    OPENROUTER = {
        "api_key": os.getenv("OPENROUTER_API_KEY"),
        "api_base_url": os.getenv("OPENROUTER_API_BASE_URL")
    }
    LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "CEREBRAS::deepseek-r1-distill-llama-70b")
    TEMPERATURE = os.getenv("TEMPERATURE", 0.1)
    MAX_TOKENS = os.getenv("MAX_TOKENS", 32768)
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    DEEPINFRA_API_TOKEN = os.getenv("DEEPINFRA_API_TOKEN")
    DEEPINFRA_BASE_URL = os.getenv("DEEPINFRA_BASE_URL")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    CODING_STANDARDS = [
        "Use snake_case for variable names",
        "Use camelCase for function names",
        "Use PascalCase for class names",
        "Use uppercase for constants"
    ]
    REVIEW_METRICS = [
        "Code complexity",
        "Code duplication",
        "Code coverage"
    ]