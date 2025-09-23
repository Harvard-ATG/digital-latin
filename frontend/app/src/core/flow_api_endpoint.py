import requests
import os
import logging

logging.getLogger(__name__)

# Mapping for level selection to system prompt code
# Corresponds to flow prompts that use DCC and Logein Word Lists.
LEVEL_TO_SYSTEM_PROMPT_ID = {
    "Level 1": "S1.3B",
    "Level 2": "S2.3B"
}

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

def convert_chat_messages_to_chat_history(messages):
    """
    Convert Streamlit chat history (list of {role, content}) to /score API chat_history format.
    Only includes user and assistant messages (ignores system messages).
    Args:
        messages (list): List of dicts with 'role' and 'content' keys.
    Returns:
        list: List of dicts with 'role' and 'parts' (list of {'text': ...}) for /score API.
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

def convert_score_response_to_streamlit_message(response_data, role="assistant"):
    """
    Convert the /score API response (JSON or raw text) to a Streamlit chat message dict.
    If response_data is a dict with 'response_text' as a string, use that; else fallback to str(response_data).
    """
    if isinstance(response_data, dict) and isinstance(response_data.get("response_text"), str):
        content = response_data["response_text"]
    else:
        content = str(response_data)
    return {"role": role, "content": content}

# Example usage (for testing, remove in production):
if __name__ == "__main__":
    # Original Streamlit chat messages (including system message)
    streamlit_messages = [
        {"role": "system", "content": "You are a helpful assistant for Latin translation."},
        {"role": "user", "content": "Help me translate the word balut to English"}
    ]
    print("Original Streamlit messages:")
    print(streamlit_messages)

    # Convert to /score API chat_history format
    chat_history = convert_chat_messages_to_chat_history(streamlit_messages)
    print("\nParsed chat_history for /score API:")
    print(chat_history)

    # Call the /score endpoint with the converted chat history
    result = call_flow_score_endpoint(
        chat_history=chat_history,
        level="Level 1"
    )
    print("\nResponse from /score endpoint:")
    print(result)
