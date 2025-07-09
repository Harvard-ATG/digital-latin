import os
import json
import requests
from typing import Any, Callable, List, Dict, Tuple, Optional
import logging
from google.genai.errors import ClientError, ServerError, APIError
from google.genai import types
import google.genai
import re
import time
import inspect
import asyncio

logging.getLogger(__name__)

class GeminiPipeline:
    def __init__(self, input_data):
        self.input_data = input_data
        self.api_url = os.getenv('GEMINI_API_URL')
        self.api_key = os.getenv('GEMINI_API_KEY')

        # Initialize logging
        self.log = logging.getLogger("gemini_pipeline")
        self.log.setLevel(logging.DEBUG)

        # Initialize model cache attributes
        self._model_cache: Optional[List[Dict[str, str]]] = None
        self._model_cache_time: float = 0

        # Initialize allowed models list
        # Print the environment variable for allowed models
        # allowed_models_env = os.getenv("GOOGLE_ALLOWED_MODELS", "gemini-2.5-pro")
        # print(f"[GeminiPipeline] GOOGLE_ALLOWED_MODELS env: {allowed_models_env}")
        # self._allowed_models_list = [model.strip() for model in allowed_models_env.split(",") if model.strip()]
        # print(f"[GeminiPipeline] Allowed models list: {self._allowed_models_list}")
        # if self._allowed_models_list:
        #     self.log.info(f"Limiting selectable models to: {self._allowed_models_list}")

    def call_gemini_api(self):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        response = requests.post(self.api_url, headers=headers, data=json.dumps(self.input_data))
        
        if response.status_code != 200:
            raise Exception(f"Gemini API call failed with status code {response.status_code}: {response.text}")
        
        return response.json()

    def run_pipeline(self):
        # Step 1: Call Gemini API
        gemini_response = self.call_gemini_api()
        
        # Step 2: Process Gemini response
        # ... processing logic ...
        
        return gemini_response

    async def pipe(
        self,
        body: dict,
        __metadata__: dict[str, Any],
        __event_emitter__: Callable,
        __tools__: dict[str, Any] | None,
    ) -> str:
        """
        Main method for sending requests to the Google Gemini endpoint.
        Now explicitly non-streaming.
        """
        request_id = id(body)
        self.log.debug(f"Processing request {request_id}")

        try:
            model_id = body.get("model", "")
            try:
                model_id = self._prepare_model_id(model_id)
                self.log.debug(f"Using model: {model_id}")
            except ValueError as ve:
                return f"Model Error: {ve}"

            stream = False
            messages = body.get("messages", [])

            contents, system_instruction = self._prepare_content(messages)
            if not contents:
                return "No content provided for generation."
            if not system_instruction:
                self.log.debug("No system instruction provided, proceeding without it.")
            self.log.debug(f"System instruction included: {system_instruction[:100]}")  # Log first 100 characters

            client = self._get_client()

            gen_config = self._configure_generation(
                body, system_instruction, model_id, __metadata__, __tools__
            )

            # Log the request details before sending
            self.log.debug(f"About to send request to Gemini API with model: {model_id}")
            self.log.debug(f"Calling generate_content (non-streaming) on client.models with model {model_id}")
            response = await self._retry_with_backoff(
                client.models.generate_content,
                model=model_id,
                contents=contents,
                config=gen_config,
            )

            # Log the response after receiving
            self.log.debug(f"Response received from Gemini API: {response}")

            return self._handle_standard_response(response)

        except ClientError as e:
            self.log.error(f"Google API Client Error: {e.message}")
            return f"Google API Client Error: {e.message}"
        except ServerError as e:
            self.log.error(f"Google API Server Error: {e.status_code} {e.message}")
            return f"Google API Server Error: {e.status_code} {e.message}"
        except APIError as e:
            self.log.error(f"Google API Error: {e.message}")
            return f"Google API Error: {e.message}"
        except ValueError as e:
            self.log.error(f"Configuration Error: {e}")
            return f"Configuration Error: {e}"
        except Exception as e:
            self.log.exception(f"An unexpected error occurred in pipe: {e}")
            return f"An unexpected error occurred: {e}"

    async def _retry_with_backoff(self, func, *args, **kwargs):
        # Only try once, no retry or timeout, just wait for the response
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return await asyncio.to_thread(func, *args, **kwargs)

    def _prepare_model_id(self, model_id: str) -> str:
        # # print(f"[GeminiPipeline] Allowed models list before model lookup: {self._allowed_models_list}")
        # print(f"[GeminiPipeline] Model selected in UI: '{model_id}'")
        # # Compare selected model to each allowed model character by character
        # for allowed in self._allowed_models_list:
        #     print(f"[GeminiPipeline] Comparing to allowed model: '{allowed}'")
        #     if model_id != allowed:
        #         diffs = []
        #         max_len = max(len(model_id), len(allowed))
        #         for i in range(max_len):
        #             c1 = model_id[i] if i < len(model_id) else '<none>'
        #             c2 = allowed[i] if i < len(allowed) else '<none>'
        #             if c1 != c2:
        #                 diffs.append(f"pos {i}: '{c1}' != '{c2}'")
        #         if diffs:
        #             print(f"[GeminiPipeline] Diff for '{model_id}' vs '{allowed}':\n  " + "\n  ".join(diffs))
        #     else:
        #         print(f"[GeminiPipeline] Model '{model_id}' matches allowed model '{allowed}' exactly.")
        """
        Prepare and validate the model ID for use with the API.
        This function will now also strip any leading/trailing whitespace.
        """
        # original_model_id = model_id
        # model_id = self.strip_prefix(
        #     original_model_id
        # )  # Ensure stripping happens here too

        # Allow models starting with 'gemini-' or 'gemma-'
        # if not (model_id.startswith("gemini-") or model_id.startswith("gemma-")):
        #     models_list = self.get_google_models()
        #     found_model = next(
        #         (m["id"] for m in models_list if m["name"] == original_model_id), None
        #     )
        #     # Ensure the found model also starts with 'gemini-' or 'gemma-'
        #     if found_model and (
        #         found_model.startswith("gemini-") or found_model.startswith("gemma-")
        #     ):
        #         model_id = found_model
        #         self.log.debug(
        #             f"Mapped model name '{original_model_id}' to model ID '{model_id}'"
        #         )
        #     else:
        #         self.log.error(
        #             f"Invalid or unsupported model ID: '{original_model_id}'"
        #         )
        #         raise ValueError(
        #             f"Invalid or unsupported Google model ID or name: '{original_model_id}'"
        #         )

        # If a list of allowed models is configured, ensure the selected model is in it
        # if self._allowed_models_list and model_id not in self._allowed_models_list:
        #     self.log.error(
        #         f"Selected model '{model_id}' is not in the allowed list: {self._allowed_models_list}"
        #     )
        #     raise ValueError(
        #         f"Selected model '{model_id}' is not an allowed model. Please choose from: {', '.join(self._allowed_models_list)}"
        #     )

        return model_id

    def strip_prefix(self, model_name: str) -> str:
        """
        Extract the model identifier using regex, handling various naming conventions.
        """
        stripped = re.sub(r"^(?:.*/|[^.]*\.)", "", model_name).strip()
        return stripped

    def get_google_models(self, force_refresh: bool = False) -> List[Dict[str, str]]:
        """
        Retrieve available Google models suitable for content generation.
        Uses caching to reduce API calls.

        Args:
            force_refresh: Whether to force refreshing the model cache

        Returns:
            List of dictionaries containing model id and name.
        """
        # Check cache first
        current_time = time.time()
        if (
            not force_refresh
            and self._model_cache is not None
            and (current_time - self._model_cache_time) < self.valves.MODEL_CACHE_TTL
        ):
            self.log.debug("Using cached model list")
            return self._model_cache

        try:
            client = self._get_client()
            self.log.debug("Fetching models from Google API")
            models = client.models.list()
            available_models = []
            for model in models:
                actions = model.supported_actions
                if actions is None or "generateContent" in actions:
                    available_models.append(
                        {
                            "id": self.strip_prefix(model.name),
                            "name": (model.display_name or self.strip_prefix(model.name)).strip(),
                        }
                    )

            self.log.debug(f"Available models from API: {[m['id'] for m in available_models]}")
            self.log.debug(f"Allowed models list: {self._allowed_models_list}")

            model_map = {model["id"]: model for model in available_models}

            # Filter map to only include models starting with 'gemini-' or 'gemma-'
            filtered_models = {
                k: v
                for k, v in model_map.items()
                if k.startswith("gem") or k.startswith("gemma")
            }

            if self._allowed_models_list:
                self.log.debug(f"Applying ALLOWED_MODELS filter: {self._allowed_models_list}")
                filtered_models = {
                    k: v
                    for k, v in filtered_models.items()
                    if k in self._allowed_models_list
                }

            self._model_cache = list(filtered_models.values())
            self._model_cache_time = current_time
            self.log.debug(f"Found {len(self._model_cache)} Gemini models")
            return self._model_cache

        except Exception as e:
            self.log.exception(f"Could not fetch models from Google: {str(e)}")
            return [{"id": "error", "name": f"Could not fetch models: {str(e)}"}]

    def _get_client(self):
        """
        Validates API credentials and returns a genai.Client instance.
        """
        api_key = os.getenv("GOOGLE_API_KEY")
        base_url = os.getenv("GOOGLE_API_BASE_URL") or "https://go.apis.huit.harvard.edu/ais-google-gemini"
        self.log.debug(f"_get_client: Using base_url: {base_url}")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set. Please provide the API key in the environment variables.")
        return google.genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(base_url=base_url),
        )

    def _prepare_content(
        self, messages: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Prepare messages content for the API and extract system message if present.
        """
        # Extract system message
        system_message = next(
            (msg["content"] for msg in messages if msg.get("role") == "system"),
            None,
        )


        # Prepare contents for the API
        contents = []
        for message in messages:
            role = message.get("role")
            if role == "system":
                continue  # Skip system messages, handled separately

            content = message.get("content", "")
            parts = []

            # Handle different content types
            if isinstance(content, list):  # Multimodal content
                parts.extend(self._process_multimodal_content(content))
            elif isinstance(content, str):  # Plain text content
                parts.append({"text": content})
            else:
                self.log.warning(f"Unsupported message content type: {type(content)}")
                continue  # Skip unsupported content

            # Map roles: 'assistant' -> 'model', 'user' -> 'user'
            api_role = "model" if role == "assistant" else "user"
            if parts:  # Only add if there are parts
                contents.append({"role": api_role, "parts": parts})

        return contents, system_message

    def _configure_generation(self, body, system_instruction, model_id, __metadata__, __tools__):
        """
        Configure the generation parameters for the Gemini API request.
        """
        # Default generation config
        gen_config = {
            "temperature": body.get("temperature", 0.7),
            "top_p": body.get("top_p", 1.0),
            "top_k": body.get("top_k", 1),
            "max_output_tokens": body.get("max_tokens", 10242),
        }
        # Add system instruction if present
        if system_instruction:
# If system_instruction is a string, log only the first 100 characters
            if isinstance(system_instruction, str):
                logging.debug(f"System instruction set: {system_instruction[:100]}")
            else:
                logging.debug(f"System instruction set: {system_instruction}")
            gen_config["system_instruction"] = system_instruction
                    # Add tools if present
        if __tools__:
            gen_config["tools"] = __tools__
        return gen_config

    def _handle_standard_response(self, response: Any) -> str:
        """
        Handle non-streaming response from Gemini API.
        """
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback and getattr(response.prompt_feedback, 'block_reason', None):
            return f"[Blocked due to Prompt Safety: {response.prompt_feedback.block_reason.name}]"

        if not hasattr(response, 'candidates') or not response.candidates:
            return "[Blocked by safety settings or no candidates generated]"

        candidate = response.candidates[0]
        if hasattr(candidate, 'finish_reason') and candidate.finish_reason == 'SAFETY':
            blocking_rating = next(
                (r for r in getattr(candidate, 'safety_ratings', []) if getattr(r, 'blocked', False)), None
            )
            reason = f" ({blocking_rating.category.name})" if blocking_rating else ""
            return f"[Blocked by safety settings{reason}]"

        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
            return "".join(
                part.text for part in candidate.content.parts if hasattr(part, "text")
            )
        else:
            return "[No content generated or unexpected response structure]"

# Example usage:
# pipeline = GeminiPipeline(input_data)
# result = pipeline.run_pipeline()