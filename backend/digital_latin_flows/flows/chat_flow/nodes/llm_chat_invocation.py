import json
import sys
import os
import time
import boto3
import requests
from promptflow.core import tool
from jinja2 import (
    Environment,
    FileSystemLoader,
    select_autoescape,
)
from botocore.exceptions import ClientError
from pathlib import Path

def find_project_root(marker=".project_root"):
    """
    Searches upwards from the current file to find the project root.
    
    The project root is identified by the presence of a marker file or directory
    (e.g., '.git', 'pyproject.toml').
    """
    # Start from the directory of the current file
    current_path = Path(__file__).resolve().parent
    while current_path != current_path.parent:
        if (current_path / marker).exists():
            return current_path
        current_path = current_path.parent
    raise FileNotFoundError(f"Project root marker '{marker}' not found.")

# Constants for model IDs and connection names
CLAUDE_3_7_SONNET_MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
CLAUDE_4_0_SONNET_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
CLAUDE_4_0_OPUS_MODEL_ID = "us.anthropic.claude-opus-4-20250514-v1:0"
DEEPSEEK_MODEL_ID = "us.deepseek.r1-v1:0"
GEMINI_MODEL_ID = "gemini-2.5-pro-preview-05-06"

# Connection names and service names
BEDROCK_CONNECTION = "bedrock_connection"
BEDROCK_SERVICE_NAME = "bedrock-runtime"
GEMINI_CONNECTION = "gemini_connection"

# Gemini API endpoints
GEMINI_BASE_URL = "https://go.apis.huit.harvard.edu/ais-google-gemini"
GEMINI_PRO_ENDPOINT = "/v1beta/models/gemini-2.5-pro:generateContent"

# Default AWS region
DEFAULT_REGION = "us-east-1"


@tool
def invoke_llm(
    chat_history: list,
    system_prompt_template_path: str,
    system_prompt_id: str,
    model_id: str,
    selector_template_variables: dict = {},
    dynamic_template_variables: dict = {},
) -> dict:
    """
    Invokes the Google Gemini model via the HUIT AI Services API Gateway.
    It renders Jinja templates for prompts before invoking the LLM.

    Args:
        chat_history (list): A list of chat messages in the format expected by the LLM.
        system_prompt_template_path (str): Relative path to the Jinja template file for the system prompt.
        system_prompt_id (str): A unique identifier for the system prompt definition/iteration.
        model_id (str): The specific Gemini model ID (e.g., "gemini-2.0-flash").
        selector_template_variables (dict): Variables from prompt_selector_node
        dynamic_template_variables (dict): Variables from flow inputs (overrides)

    Returns:
        dict: A dictionary containing the LLM's response and other metadata.
              Includes the *rendered* prompts used for reporting, and the prompt_id.
    """
    try:
        PROJECT_ROOT_FOR_TEMPLATES = find_project_root()
        print(f"Rendering prompts from templates in {PROJECT_ROOT_FOR_TEMPLATES}", file=sys.stderr)

        print("Merging template variables...", file=sys.stdout)
        merged_template_variables = {
            **selector_template_variables,
            **dynamic_template_variables,
        }
        print("Merged the Template Variables: ", file=sys.stdout)

        # Set up Jinja2 environment to load templates from the project root
        env = Environment(
            loader=FileSystemLoader(PROJECT_ROOT_FOR_TEMPLATES),
            autoescape=select_autoescape(["html", "xml"]),
        )

        rendered_user_prompt = ""
        rendered_system_prompt = ""

        truncated_chat_history = []
        for message in chat_history:
            
            # Copy the message structure
            new_message = message.copy()

            # Copy the parts list
            new_parts = []
            for part in message.get("parts", []):

                # Truncate the text if present
                if "text" in part:
                    truncated_text = part["text"][:20] + ("..." if len(part["text"]) > 20 else "")
                    new_parts.append({"text": truncated_text})
                else:
                    new_parts.append(part.copy())
            new_message["parts"] = new_parts
            truncated_chat_history.append(new_message)
        
        rendered_user_prompt = truncated_chat_history

        try:

            system_template_full_path = os.path.join(PROJECT_ROOT_FOR_TEMPLATES, system_prompt_template_path)
            print(f"System template full path: {system_template_full_path}", file=sys.stderr)
            
            if not os.path.isfile(system_template_full_path):
                print(f"ERROR: System template file does not exist: {system_template_full_path}", file=sys.stderr)
            
            
            # Render System Prompt Template
            system_template = env.get_template(system_prompt_template_path)
            rendered_system_prompt = system_template.render(merged_template_variables)

        except Exception as e:
            return {"Error": f"Failed to render Jinja template(s): {e}", "status": "failed"}
        
    except Exception as e:
        print(f"Error: An error occurred while rendering prompts: {e}", file=sys.stderr)

    if "gemini" in model_id.lower():
        try:
            # Directly get Gemini API key and base URL
            try:
                api_key = os.environ["GEMINI_API_KEY"]
                base_url = os.environ.get("GEMINI_BASE_URL", GEMINI_BASE_URL)
            except Exception as e:
                return {"error": f"Missing Gemini API credentials: {e}", "status": "failed"}

            api_endpoint = f"{base_url}{GEMINI_PRO_ENDPOINT}"
            payload = {
                "contents": chat_history,
                "generationConfig": {
                    "maxOutputTokens": 65536,
                }
            }
            if rendered_system_prompt:
                payload["system_instruction"] = {
                    "parts": [{"text": rendered_system_prompt}]
                }
            headers = {"Content-Type": "application/json", "api-key": api_key}
            start_time = time.time()
            try:
                print(f"Calling Gemini API at {api_endpoint} with payload: {json.dumps(payload)[:500]}...", file=sys.stdout)
                response = requests.post(api_endpoint, headers=headers, json=payload)
                response.raise_for_status()
            except requests.exceptions.HTTPError as http_err:
                print(f"HTTP error occurred: {http_err}", file=sys.stderr)
                return {
                    "system_prompt_id": system_prompt_id,
                    "model_id_used": model_id,
                    "user_prompt_used": rendered_user_prompt,
                    "system_prompt_used": rendered_system_prompt,
                    "response_text": f"HTTP error occurred: {http_err}",
                    "full_api_response": {},
                    "llm_run_time": 0,
                    "status": "failed",
                    "error": f"HTTP error occurred: {http_err}"
                }
            response_json = response.json()
            full_api_response = response_json
            llm_text_response = ""
            if response_json and response_json.get("candidates"):
                for candidate in response_json["candidates"]:
                    if candidate.get("content") and candidate["content"].get("parts"):
                        for part in candidate["content"]["parts"]:
                            if part.get("text"):
                                llm_text_response += part["text"]
            end_time = time.time()
            duration = end_time - start_time

            # The ouput for the Gemini LLM Call
            llm_node_invocation_output = {
                "system_prompt_id": system_prompt_id,
                "model_id_used": model_id,
                "user_prompt_used": rendered_user_prompt,
                "system_prompt_used": rendered_system_prompt,
                "response_text": llm_text_response,
                "full_api_response": full_api_response,
                "llm_run_time": duration,
                "status": "success",
            }

            return llm_node_invocation_output
        
        except Exception as e:
            print(f"Error: An error occurred while invoking Gemini API: {e}", file=sys.stderr)
            return {
                "system_prompt_id": system_prompt_id,
                "model_id_used": model_id,
                "user_prompt_used": rendered_user_prompt,
                "system_prompt_used": rendered_system_prompt,
                "response_text": f"HTTP error occurred: {e}",
                "full_api_response": {},
                "llm_run_time": 0,
                "status": "failed",
                "error": f"An unexpected error occurred: {e}"
            }
    else:
        try:
            # Directly get AWS credentials
            try:
                aws_access_key_id = os.environ["AWS_AI_WORKFLOW_CORE_DEV_ID"]
                aws_secret_access_key = os.environ["AWS_AI_WORKFLOW_CORE_DEV_SECRET"]
                aws_region = os.environ.get("AWS_DEFAULT_REGION", DEFAULT_REGION)
            except Exception as e:
                return {"error": f"Missing AWS credentials: {e}", "status": "failed"}
            bedrock_runtime = boto3.client(
                service_name="bedrock-runtime",
                region_name=aws_region,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
            )

            # Prepare the request body based on the model_id
            body = {}
            llm_text_response = ""
            full_api_response = {}

            if "claude" in model_id.lower() and model_id.lower() in [
                CLAUDE_3_7_SONNET_MODEL_ID,
                CLAUDE_4_0_OPUS_MODEL_ID,
                CLAUDE_4_0_SONNET_MODEL_ID,
            ]:
                print(f"The claude model is {model_id}", file=sys.stderr)
                messages = []
                messages.append({"role": "user", "content": rendered_user_prompt})

                body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 5000,  # Adjust as needed - Temporarily removed for defualt model response. Initially used 64000, for Claude 4 set to 5000
                    "messages": messages,
                }

                if rendered_system_prompt:
                    body["system"] = rendered_system_prompt

            elif "deepseek" in model_id.lower():
                # Deepseek's response format is similar to OpenAI chat completions
                messages = []
                if rendered_system_prompt:
                    messages.append(
                        {"role": "system", "content": rendered_system_prompt}
                    )
                messages.append({"role": "user", "content": rendered_user_prompt})

                body = {
                    "messages": messages,
                    "stream": False,
                    "max_tokens": 32000
                }

            else:
                raise ValueError(
                    f"Unsupported model_id for Bedrock: {model_id}. Please ensure it's a support Claude or Deepseek model in this flow",
                    file=sys.stderr,
                )

            print(
                f"Invoking Bedrock model: {model_id}",
                file=sys.stderr,
            )

            start_time = time.time()
            response = bedrock_runtime.invoke_model(
                body=json.dumps(body),
                modelId=model_id,
                accept="application/json",
                contentType="application/json",
            )
            full_api_response = json.loads(response["body"].read())

            # Parse response based on model type
            if "claude" in model_id.lower():
                if full_api_response.get("content"):
                    for content_block in full_api_response["content"]:
                        if content_block.get("type") == "text":
                            llm_text_response += content_block["text"]

            elif "deepseek" in model_id.lower():
                if full_api_response.get("choices") and full_api_response["choices"][
                    0
                ].get("message"):
                    llm_text_response = full_api_response["choices"][0]["message"].get(
                        "content", ""
                    )
            end_time = time.time()
            duration = end_time - start_time  # Duration in seconds

            print('text_response', llm_text_response, file=sys.stderr)

            llm_node_invocation_output = {
                "system_prompt_id": system_prompt_id,
                "model_id_used": model_id if type(model_id) == str else "PROBLEM",
                "response_text": llm_text_response,
                "full_api_response": full_api_response,
                "user_prompt_used": rendered_user_prompt,  # Return the RENDERED user prompt
                "system_prompt_used": rendered_system_prompt,  # Return the RENDERED system prompt
                "llm_run_time": duration,
                "status": "success",
            }
            return llm_node_invocation_output

        except ClientError as e:
            return {
                "error": f"Bedrock Client Error: {e.response['Error']['Message']}",
                "status": "failed",
            }
        except ValueError as e:
            return {"error": f"Configuration or Payload Error: {e}", "status": "failed"}
        except Exception as e:
            return {"error": f"An unexpected error occurred: {e}", "status": "failed"}
