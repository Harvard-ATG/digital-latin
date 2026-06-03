# Digital Latin - Agent Guidelines

## Project Overview

Latin passage simplification tool for instructors. Uses AI to simplify authentic classical Latin texts for students at different proficiency levels (Level 1: first-year, Level 2: second-year).

## Architecture

- **Frontend**: Streamlit UI (`frontend/app/src/core/streamlit_ui_chatapi.py`) - port 8502
- **Backend**: PromptFlow-based Flow API (`backend/digital_latin_flows/`) - port 8080 (legacy, retained for non-streaming path)
- **Database**: PostgreSQL for session persistence - port 5432
- **External APIs**: Google Gemini (via HUIT Apigee proxy), AWS Bedrock (Claude), OpenAI (via HUIT Apigee proxy)

## Key Files

| File | Purpose |
|------|---------|
| `frontend/app/src/core/streamlit_ui_chatapi.py` | Main Streamlit app - UI, auth, chat, session management |
| `frontend/app/src/core/flow_api_endpoint.py` | Streaming API clients (Gemini, Claude, OpenAI) + legacy backend `/score` client |
| `frontend/app/src/core/prompt_builder.py` | Builds system prompts from backend Jinja2 templates + vocabulary CSVs |
| `frontend/app/src/core/prompt_data/` | DCC and Logeion vocabulary CSVs injected into system prompts |
| `frontend/app/src/core/session_db_postgres.py` | PostgreSQL session persistence |
| `backend/digital_latin_flows/tooling/prompts/system/` | Jinja2 system prompt templates (source of truth) |
| `backend/digital_latin_flows/flows/chat_flow/nodes/llm_chat_invocation.py` | Backend LLM invocation (legacy non-streaming path) |
| `docker-compose.yml` | Container orchestration |
| `.env` / `.env.example` | Environment configuration |

## How Requests Flow

### Streaming path (current, frontend-direct)

1. User enters Latin text in Streamlit UI
2. `prompt_builder.py` loads the Jinja2 template + vocabulary data to build the full system prompt
3. `flow_api_endpoint.py` → `stream_response()` routes to the correct provider:
   - Gemini → HUIT Apigee proxy (`go.apis.huit.harvard.edu/ais-google-gemini`)
   - Claude → AWS Bedrock via boto3 (`converse_stream`)
   - OpenAI → HUIT Apigee proxy (`go.apis.huit.harvard.edu/ais-openai-direct-limited-schools`)
4. Tokens stream back and render via `st.write_stream` inside `st.chat_message`

### Legacy path (backend, non-streaming)

1. Frontend calls `call_flow_score_endpoint()` → POST to backend `/score`
2. Backend `prompt_selector_node` picks the Jinja2 prompt template
3. Backend `llm_chat_node` routes to Gemini or Bedrock based on `model_id`
4. Full response returns to UI

## Model Configuration

- `ALLOWED_MODELS` (or fallback `GOOGLE_ALLOWED_MODELS`) env var controls the frontend dropdown
- Models available: Gemini 2.5 Pro, 3.1 Pro, 3.5 Flash, 2.5 Flash, Claude Sonnet 4.6, Claude Opus 4.6, GPT-5.4
- High reasoning toggle: enables deep thinking for all providers (thinkingBudget/thinkingLevel for Gemini, extended thinking for Claude, reasoning_effort for OpenAI)
- Gemini uses HUIT Apigee (`go.apis.huit.harvard.edu/ais-google-gemini`) with `api-key` header
- Claude uses AWS Bedrock credentials via boto3
- OpenAI uses HUIT Apigee (`go.apis.huit.harvard.edu/ais-openai-direct-limited-schools`) with `api-key` header

## Development

```bash
cp .env.example .env   # configure API keys
docker-compose up --build
# Frontend: http://localhost:8502
# Backend: http://localhost:8080 (legacy, not required for streaming)
```

## Constraints

- This is a dev/local tool only - production changes go through separate Terraform/ECS pipeline
- Auth is simple shared credentials via env vars (not SSO)
- The backend is retained but not required for the streaming path
- The HUIT Apigee proxies require `api-key` header (not query param)
- System prompts are sourced from `backend/digital_latin_flows/tooling/prompts/system/` — keep as single source of truth
