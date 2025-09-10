import pandas as pd
from promptflow.core import tool
from digital_latin_flows.tooling.utilities.prompt_registry_util import (
    get_system_prompt,
    get_user_prompt,
    get_judge_prompt
)
from typing import Dict, Any, Optional
from pathlib import Path
import json

# Base paths for prompt templates and results
PROMPT_TEMPLATES_BASE_PATH = Path("digital_latin_flows/tooling/prompts/")
RESULTS_BASE_PATH = Path("digital_latin_flows/results/")

@tool
def prompt_selector(
    system_prompt_id: Optional[str] = None,
    user_prompt_id: Optional[str] = None,
    judge_prompt_id: Optional[str] = None,
    judge_user_prompt_id: Optional[str] = None,
    report_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    The prompt selector tool takes in prompt IDs and returns Jinja template paths and default template variables based on those IDs.
    At least one prompt ID must be provided. Returns a dictionary with template paths and variables for prompt rendering in an LLM or Judge Node.
    """
    # Create an empty prompt configuration dictionary
    prompt_config = {}

    # Define subfolder paths for each prompt type
    SYSTEM_PROMPT_DIR = PROMPT_TEMPLATES_BASE_PATH / "system"
    USER_PROMPT_DIR = PROMPT_TEMPLATES_BASE_PATH / "user"
    JUDGE_SYSTEM_PROMPT_DIR = PROMPT_TEMPLATES_BASE_PATH / "judge/system"
    JUDGE_USER_PROMPT_DIR = PROMPT_TEMPLATES_BASE_PATH / "judge/user"

    # Validation: at least one prompt ID of any type must be provided
    if not (system_prompt_id or user_prompt_id or judge_prompt_id or judge_user_prompt_id):
        raise ValueError("At least one prompt ID must be provided.")

    try:
        # Resolve filenames for each prompt type using registry utilities
        # The registry utility contains mappings from prompt IDs to their file paths
        system_prompt_filename = get_system_prompt(key=system_prompt_id) if system_prompt_id else None
        user_prompt_filename = get_user_prompt(key=user_prompt_id) if user_prompt_id else None
        judge_system_prompt_filename = get_judge_prompt(key=judge_prompt_id, prompt_type="system") if judge_prompt_id else None
        judge_user_prompt_filename = get_judge_prompt(key=judge_user_prompt_id, prompt_type="user") if judge_user_prompt_id else None

        # Load template variables from CSV files in the prompt data directory
        # These variables make the prompts more dynamic and context-aware
        # For digital-latin, CSV contains domain specific word lists
        template_variables = {}
        script_dir = Path(__file__).parent

        prompt_data_directory_path = (script_dir / "../../data/prompt_data").resolve()
        csv_files = list(prompt_data_directory_path.glob("*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in prompt data folder: {prompt_data_directory_path}")
        for file_path in csv_files:
            key = file_path.stem  # Use filename (without extension) as variable key
            try:
                # Using pandas because it particularly excels at handling tabular data
                data_frame = pd.read_csv(file_path)  # Read CSV into a DataFrame
                text_data = data_frame.to_csv(index=False)  # Convert the DataFrame to text data
                template_variables[key] = text_data  # Store in template variables by key
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

        # For the judge node, we can take advantage of the existing report data produced by the LLM
        # We can pass this report data to the Judge LLM
        if report_id is not None:
            report_path = script_dir.parent / "results" / f"llm_report_{report_id:05}.json"
            if report_path.exists():
                try:
                    with open(report_path, encoding="utf8") as f:
                        report_data = json.load(f)
                    # Extract key fields for template use
                    template_variables["original_passage_text"] = report_data.get("user_prompt_used", "")
                    llm_invocation_output = report_data.get("llm_invocation_output", {})
                    template_variables["original_llm_response_text"] = llm_invocation_output.get("response_text", "")
                    template_variables["system_prompt_id"] = report_data.get("system_prompt_id", "")
                    template_variables["user_prompt_id"] = report_data.get("user_prompt_id", "")
                except Exception as e:
                    print(f"Error reading report JSON for report_id {report_id}: {e}")
            else:
                print(f"Report file not found for report_id {report_id}: {report_path}")

        # Builds the final output dictionary with resolved template paths
        # The dictionary is passed to the LLM node for rendering
        if system_prompt_filename:
            prompt_config["system_prompt_template_path"] = str(SYSTEM_PROMPT_DIR / system_prompt_filename)
        if user_prompt_filename:
            prompt_config["user_prompt_template_path"] = str(USER_PROMPT_DIR / user_prompt_filename)
        if judge_system_prompt_filename:
            prompt_config["judge_prompt_template_path"] = str(JUDGE_SYSTEM_PROMPT_DIR / judge_system_prompt_filename)
        if judge_user_prompt_filename:
            prompt_config["judge_user_prompt_template_path"] = str(JUDGE_USER_PROMPT_DIR / judge_user_prompt_filename)
        prompt_config["template_variables"] = template_variables  # All loaded variables for template rendering
        return prompt_config

    except Exception as e:
        # Raise a clear error if anything fails during prompt selection
        raise ValueError(f"An issue arose during prompt selection: {e}")