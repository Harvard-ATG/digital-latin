# CLAUDE.md

See [agents.md](agents.md) for project context, architecture, key files, and development guidelines.

## Quick Reference

- This branch (`feature/update-models`) is dev-only — prod remains unchanged on `main`
- Frontend streams directly to LLM APIs (no backend needed for chat)
- System prompts live in `backend/.../prompts/system/` — `prompt_builder.py` reads them at runtime
- Models: Gemini (HUIT Apigee), Claude (AWS Bedrock), OpenAI (HUIT Apigee)
- High reasoning toggle controls thinking depth across all providers
- Backend `/score` endpoint still exists for legacy/non-streaming use
- No prod/dev feature flags needed — dev deploys this branch, prod deploys main
