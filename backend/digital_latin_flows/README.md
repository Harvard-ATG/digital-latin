# Backend Service: AI Workflow with Promptflow

Our backend is a self-contained AI workflow service powered by [Promptflow](https://github.com/microsoft/promptflow), which we originally used for testing various interations of prompts and llms in our tool. It is a robust framework for building and orchestrating AI applications. Promptflow allows us to manage our generative AI logic in a clear, modular, and scalable way, supporting advanced features such as prompt engineering, multi-model orchestration, and modular logic via flows and custom nodes.

Promptflow packages are used in this tool, but broader functionality or the VS Code Extension is not leveraged in this backend implementation.
---

## What is a "Flow"?

A **flow** is a self-contained AI application or workflow. An AI workflow is a step-by-step process that utilizes artificial intelligence to automate tasks, analyze data, and enhance decision-making . In Promptflow, each flow is defined in a `flow.dag.yaml` file, which acts as the definitive blueprint for our AI logic—specifying all operations and their sequence, inputs and outputs, and data dependencies.

---

## Understanding the Workflow: The DAG

Promptflow represents workflows as **Directed Acyclic Graphs (DAGs)**—think of these as one-way flowcharts where data moves from inputs through a sequence of nodes to a final output. This structure makes our backend logic:
- Easy to visualize and reason about
- Modular and reusable
- Reliable and debuggable

### Our Workflow: Example DAG

Key elements of our primary flow see [`flows/chat_flow/flow.dag.yaml`](flows/chat_flows/flow.dag.yaml):

- **Inputs:**  
  - `system_prompt_id`: Chooses the desired task or prompt strategy
  - `chat_history`: Supplies context or previous conversation turns
  - `llm_model_id`: Selects which large language model to use

- **Nodes:**  
  - `prompt_selector_node`: Dynamically selects the correct prompt template based on `system_prompt_id`
  - `llm_chat_node`: Sends the prompt (plus user/chat context) to the specified LLM and collects the model response

- **Data Flow:**  
  Data flows explicitly from node to node as mapped in `flow.dag.yaml`. For example, the chosen prompt from `prompt_selector_node` feeds directly as input into `llm_chat_node`, ensuring an auditable, reproducible, and adaptable sequence of operations.

---

## Components

### Flows (`flows/`)
Houses Promptflow DAG definitions and their associated Python nodes and prompt templates. Each subdirectory contains a distinct flow for a particular AI task—ranging from simple LLM calls to advanced multi-model orchestration.

### Prompts (`prompts/`)
Organizes Jinja2 templates for both "system" and "user" prompts. This modular approach enables rapid prompt engineering and easy adaptation of prompts as models and pedagogical needs evolve.

  - `system/`: General role instructions/persona prompts (e.g., `general_neutral_system.jinja2`)
  - `user/`: User-facing prompt structures (e.g., `basic_qa_user.jinja2`)

### Tools (`tools/`)

This directory contains custom Python modules that extend core Promptflow node functionality. Tools are integrated directly as nodes in Promptflow DAGs, enabling sophisticated and reusable logic within a workflow.

- **`prompt_selector_tool.py`**:  
  Implements dynamic prompt selection for the workflow. Given parameters such as `system_prompt_id`, this tool programmatically chooses the appropriate prompt template, enabling context-sensitive, flexible prompt engineering. This logic lets flows adapt to a variety of tasks and user inputs without manual intervention or hardcoding. This tool levarages the `prompt_registry_util.py` in the Utilities section below.

(You can add descriptions for additional tools here as they are developed.)

### Utilities (`utilities/`)

This folder provides general-purpose Python utilities that support and streamline the backend workflow. Utilities typically encapsulate logic that is shared across multiple nodes, nodes and scripts, or other code components.

- **`prompt_registry_util.py`**:  
  Centralizes the management of prompt templates used throughout the system. This utility can:
  - Find and retrieve Jinja2 prompt templates from the `prompts/` directory,
  - **Register new templates**
  - Provide lookup or caching to accelerate repeated prompt accesses during session runtime.

Utilities are designed to increase efficiency, ensure consistent prompt usage, and reduce code duplication throughout the backend codebase.

---

## Development and Deployment

Promptflow supports the full development lifecycle:

- **Local Development:**  
  Develop and test flows using the Promptflow extension for Visual Studio Code. The visual DAG editor streamlines rapid iteration and debugging. The use of devcontainers for the [VS Code Extension](https://microsoft.github.io/promptflow/how-to-guides/develop-a-dag-flow/quick-start.html#quick-start) functionality means the editor is functional using a local VS Code instance or the VS Code Editor that can be launched in [Github Codespaces](https://github.com/features/codespaces)

- **Deployment:**  
  Build stable flows into Docker containers using the Promptflow CLI. This bundles all dependencies and logic, ensuring consistent execution anywhere (e.g., dev, staging, or production). More on deploying flows to Docker [here](https://microsoft.github.io/promptflow/how-to-guides/deploy-a-flow/deploy-using-docker.html)

- **Repository Structure:**  
  - All live flows: `digital_latin_flows/flows/`
  - Prompts, tools, utilities, and scripts organized in subfolders for maintainability
