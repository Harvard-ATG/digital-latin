# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
- Ongoing improvements and refactoring.

## [2025-07-07]
- Renamed `app.py` to `streamlit_ui_main.py` and `app_chatapi.py` to `streamlit_ui_chatapi.py` for clarity.
- Updated all references in documentation and Docker Compose to use new filenames.
- Consolidated `README.md` and `README_ngrok.md` into a single, comprehensive `README.md`.
- Added Dockerfile and docker-compose.yml for containerized development and deployment.
- Added instructions for using ngrok to share local apps.
- Improved file structure: grouped prompts, data, and documentation into dedicated folders (`prompts/`, `data/`, `docs/`).
- Added `.env.example` for environment variable guidance.

## [Earlier]
- Added sidebar session management with session listing, deletion, and improved layout.
- Implemented system prompt selection using Jinja2 templates with fallback logic.
- Enhanced chat rendering with custom HTML, markdown, and copy-to-clipboard functionality.
- Enabled session save/load using SQLite database.
- Addressed Streamlit widget key uniqueness and rerun logic for robust state management.
- Improved prompt file selection and fallback handling.
- Added troubleshooting and usage documentation.

---

For detailed design notes and technical decisions, see `docs/notes.md`.
