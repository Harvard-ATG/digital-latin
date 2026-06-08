import requests
import json
import os
import logging
import boto3

logging.getLogger(__name__)

# Mapping for level selection to system prompt code
# Corresponds to flow prompts that use DCC and Logein Word Lists.
LEVEL_TO_SYSTEM_PROMPT_ID = {
    "Level 1": "S1.3B",
    "Level 2": "S2.3B"
}

GEMINI_STREAMING_BASE_URL = "https://go.apis.huit.harvard.edu/ais-google-gemini"
OPENAI_BASE_URL = "https://go.apis.huit.harvard.edu/ais-openai-direct-limited-schools/v1"
DEFAULT_AWS_REGION = "us-east-1"


# =============================================================================
# Backend /score endpoint integration (non-streaming, original flow)
# =============================================================================

def get_system_prompt_id(level: str) -> str:
    """Map user-friendly level to system prompt code."""
    system_prompt_id = LEVEL_TO_SYSTEM_PROMPT_ID.get(level)
    logging.debug(f"Resolved {level} to prompt ID: {system_prompt_id}")
    return system_prompt_id


def call_flow_score_endpoint(
    chat_history: list,
    level: str,
    llm_model_id: str = "gemini-2.5-pro",
    api_url: str = None
) -> dict:
    """
    Send a request to the /score endpoint and return the response.
    Args:
        chat_history (list): List of previous chat messages in /score API format.
        level (str): Level selection (e.g., 'Level 1', 'Level 2').
        llm_model_id (str): Model to use (default: 'gemini-2.5-pro').
        api_url (str): The /score endpoint URL (default: from env or fallback).
    Returns:
        dict: The parsed JSON response from the endpoint.
    """
    if api_url is None:
        api_url = os.environ["FLOW_API_URL"]
    if not chat_history:
        raise ValueError("chat_history must be provided and non-empty.")
    payload = {
        "dynamic_template_variables": {},
        "llm_model_id": llm_model_id,
        "system_prompt_id": get_system_prompt_id(level),
        "chat_history": chat_history
    }
    logging.debug(f"FAE: Calling /score endpoint with payload: {payload}")
    headers = {"Content-Type": "application/json"}
    max_retries = 1  # Only one retry (total 2 attempts) to avoid excessive retries given long response times
    # Retry logic to handle potential timeouts or transient errors
    # This is a simple retry mechanism that will retry once if the request fails
    # It can be extended with more sophisticated logic if needed.
    # Note: Streamlit will handle the error if it occurs, so we raise the exception
    # to be caught by Streamlit's error handling logic to avoid blocking the Streamlit app with long waits.
    attempt = 0
    while attempt <= max_retries:
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            response_data = response.json()
            streamlit_response = convert_score_response_to_streamlit_message(response_data)
            logging.debug(f"FAE: Received response from /score endpoint: {response_data}")
            logging.debug(f"FAE: Converted response for Streamlit: {streamlit_response}")
            return streamlit_response
        except requests.RequestException as e:
            if attempt == max_retries:
                logging.error(f"FAE: Failed to call /score endpoint after {max_retries + 1} attempts: {e}")
                raise e  # Raise the actual error to be caught by Streamlit logic
            attempt += 1


def convert_score_response_to_streamlit_message(response_data, role="assistant"):
    """
    Convert the /score API response (JSON or raw text) to a Streamlit chat message dict.
    """
    if isinstance(response_data, dict) and isinstance(response_data.get("response_text"), str):
        content = response_data["response_text"]
    else:
        content = str(response_data)
    return {"role": role, "content": content}


# =============================================================================
# Direct streaming endpoints (bypass backend)
# =============================================================================

def stream_response(chat_history: list, model_id: str, system_prompt: str = None, high_reasoning: bool = True):
    """
    Route to the appropriate streaming method based on model_id.
    Yields text chunks as they arrive.
    """
    if "gemini" in model_id.lower():
        yield from stream_gemini_response(chat_history, model_id, system_prompt, high_reasoning)
    elif "anthropic" in model_id.lower() or "claude" in model_id.lower():
        yield from stream_claude_response(chat_history, model_id, system_prompt, high_reasoning)
    elif "gpt" in model_id.lower() or "o3" in model_id.lower() or "o4" in model_id.lower():
        yield from stream_openai_response(chat_history, model_id, system_prompt, high_reasoning)
    else:
        raise ValueError(f"Unknown model provider for model_id: {model_id}")


def stream_gemini_response(chat_history: list, model_id: str = "gemini-2.5-pro", system_prompt: str = None, high_reasoning: bool = True):
    """
    Stream tokens from the Gemini streamGenerateContent endpoint.
    Yields text chunks as they arrive.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set in environment.")

    url = f"{GEMINI_STREAMING_BASE_URL}/v1beta/models/{model_id}:streamGenerateContent"
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "api-key": api_key,
    }
    payload = {"contents": chat_history}
    if system_prompt:
        payload["systemInstruction"] = {
            "parts": [{"text": system_prompt}]
        }
    # Gemini 3.x uses thinkingLevel, 2.5 uses thinkingBudget
    if high_reasoning:
        if "3." in model_id:
            payload["generationConfig"] = {
                "thinkingConfig": {"thinkingLevel": "high"}
            }
        elif "2.5" in model_id:
            payload["generationConfig"] = {
                "thinkingConfig": {"thinkingBudget": 8192}
            }

    logging.debug(f"FAE: Streaming from {url} with model {model_id}")

    response = requests.post(url, json=payload, headers=headers, stream=True, timeout=120)
    response.raise_for_status()

    for line in response.iter_lines():
        if not line:
            continue
        decoded = line.decode("utf-8")
        if decoded.startswith("data: "):
            decoded = decoded[6:]
        try:
            chunk = json.loads(decoded)
            candidates = chunk.get("candidates", [])
            for candidate in candidates:
                parts = candidate.get("content", {}).get("parts", [])
                for part in parts:
                    # Only yield text parts, skip thought parts
                    if "text" in part and "thought" not in part:
                        text = part["text"]
                        if text:
                            yield text
        except json.JSONDecodeError:
            continue


def stream_claude_response(chat_history: list, model_id: str, system_prompt: str = None, high_reasoning: bool = True):
    """
    Stream tokens from Claude via AWS Bedrock converse_stream API.
    Yields text chunks as they arrive.
    """
    aws_access_key = os.environ.get("AWS_AI_WORKFLOW_CORE_DEV_ID")
    aws_secret_key = os.environ.get("AWS_AI_WORKFLOW_CORE_DEV_SECRET")
    aws_region = os.environ.get("AWS_DEFAULT_REGION", DEFAULT_AWS_REGION)

    if aws_access_key and aws_secret_key:
        client = boto3.client(
            "bedrock-runtime",
            region_name=aws_region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
        )
    else:
        client = boto3.client("bedrock-runtime", region_name=aws_region)

    # Convert Gemini-format chat_history to Bedrock messages format
    messages = []
    for msg in chat_history:
        role = msg.get("role", "user")
        if role == "model":
            role = "assistant"
        text = ""
        for part in msg.get("parts", []):
            if "text" in part:
                text += part["text"]
        messages.append({"role": role, "content": [{"text": text}]})

    logging.debug(f"FAE: Streaming from Bedrock with model {model_id}")

    kwargs = {
        "modelId": model_id,
        "messages": messages,
        "inferenceConfig": {"maxTokens": 16384},
    }
    if high_reasoning:
        kwargs["additionalModelRequestFields"] = {
            "thinking": {"type": "enabled", "budget_tokens": 10000}
        }
    else:
        kwargs["inferenceConfig"]["temperature"] = 0.7
    if system_prompt:
        kwargs["system"] = [{"text": system_prompt}]

    response = client.converse_stream(**kwargs)

    for event in response["stream"]:
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            text = delta.get("text", "")
            if text:
                yield text


def stream_openai_response(chat_history: list, model_id: str, system_prompt: str = None, high_reasoning: bool = True):
    """
    Stream tokens from OpenAI via HUIT proxy (SSE streaming).
    Yields text chunks as they arrive.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in environment.")

    base_url = os.environ.get("OPENAI_API_BASE_URL", OPENAI_BASE_URL)
    url = f"{base_url}/chat/completions"

    # Convert Gemini-format chat_history to OpenAI messages format
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for msg in chat_history:
        role = msg.get("role", "user")
        if role == "model":
            role = "assistant"
        text = ""
        for part in msg.get("parts", []):
            if "text" in part:
                text += part["text"]
        messages.append({"role": role, "content": text})

    headers = {
        "Content-Type": "application/json",
        "api-key": api_key,
    }
    payload = {
        "model": model_id,
        "messages": messages,
        "stream": True,
    }
    # Reasoning models (o-series, gpt-5+) don't support temperature but accept reasoning_effort
    is_reasoning = model_id.startswith("o") or "gpt-5" in model_id
    if is_reasoning:
        payload["reasoning_effort"] = "high" if high_reasoning else "low"
    else:
        payload["temperature"] = 0.7

    logging.debug(f"FAE: Streaming from OpenAI at {url} with model {model_id}")

    response = requests.post(url, json=payload, headers=headers, stream=True, timeout=120)
    response.raise_for_status()

    for line in response.iter_lines():
        if not line:
            continue
        decoded = line.decode("utf-8")
        if decoded.startswith("data: "):
            decoded = decoded[6:]
        if decoded.strip() == "[DONE]":
            break
        try:
            chunk = json.loads(decoded)
            choices = chunk.get("choices", [])
            for choice in choices:
                delta = choice.get("delta", {})
                text = delta.get("content", "")
                if text:
                    yield text
        except json.JSONDecodeError:
            continue


# =============================================================================
# Shared utilities
# =============================================================================

def convert_chat_messages_to_chat_history(messages):
    """
    Convert Streamlit chat history (list of {role, content}) to Gemini-format chat_history.
    Only includes user and assistant messages (ignores system messages).
    """
    chat_history = []
    for m in messages:
        if m["role"] == "user":
            chat_history.append({
                "role": m["role"],
                "parts": [{"text": m["content"]}]
            })
        if m["role"] == "assistant":
            chat_history.append({
                "role": "model",
                "parts": [{"text": m["content"]}]
            })
    return chat_history
