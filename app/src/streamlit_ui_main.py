import os
import json
import asyncio
# import datetime
import streamlit as st
import markdown2
import sentry_sdk
from pathlib import Path
from gemini_pipeline import GeminiPipeline as Pipe
from jinja2 import Template

# Initialize Sentry for error tracking
# sentry_sdk.init(
#     dsn="https://<your-public-key>@o<org-id>.ingest.sentry.io/<project-id>",
#     traces_sample_rate=1.0,  # Optional: for performance monitoring
# )


# Load environment variables
# WHY: Allows configuration (e.g., allowed models, API keys) to be set outside the code for flexibility and security.
env_file = Path(__file__).parent / "../.env"
if env_file.exists():
    with open(env_file) as f:
        env_vars = dict(
            line.strip().split("=", 1) for line in f if "=" in line.strip()
        )
        os.environ.update(env_vars)

# Initialize Gemini pipeline
# WHY: Encapsulates LLM API logic and allows for easy swapping or extension of model backends.
pipe = Pipe(input_data={})

# Define prompts
# WHY: Prompts are stored as Jinja2 templates for easy editing and reuse. This allows for level-specific instructions.
PROMPTS_DIR = Path(__file__).parent
LEVEL_1_PROMPT_JINJA = next(PROMPTS_DIR.glob("*level1*.jinja*"), None)
LEVEL_2_PROMPT_JINJA = next(PROMPTS_DIR.glob("*level2*.jinja*"), None)

def render_jinja_prompt(jinja_path, context=None):
    # WHY: Allows dynamic rendering of prompt templates with context variables.
    if jinja_path and jinja_path.exists():
        template = Template(jinja_path.read_text())
        return template.render(context or {})
    return ""


# --- SIDEBAR ---
# WHY: The sidebar provides navigation, settings, and session management. It is the main entry point for users to select models, levels, and manage their work.
with st.sidebar:
    st.title("pAIdagogue")
    st.markdown("Translate your messages to Latin (Level I or II).\n\nSelect your translation level and manage your session.")
    st.markdown("---")
    st.header("Settings")
    allowed_models_env = os.getenv("GOOGLE_ALLOWED_MODELS", "gemini-2.5-pro")
    allowed_models = [m.strip() for m in allowed_models_env.split(",") if m.strip()]
    # WHY: Model selection is now defaulted to gemini-2.5-pro and removed from the UI.
    selected_model = "gemini-2.5-pro"
    st.session_state["selected_model_chatapi"] = selected_model
    level = st.selectbox("Select Level", ["Level I", "Level II"], key="level_chatapi")
    context = {}  # Add any dynamic context if needed

    # --- DB BACKEND SELECTION ---
    # WHY: For now, default to PostgreSQL and deactivate the backend selector. To re-enable SQLite, uncomment the selector below.
    # backend = st.selectbox(
    #     "Session DB Backend",
    #     options=["Select a database backend...", "sqlite", "postgres"],
    #     index=0,
    #     help="Choose which database backend to use for saving sessions."
    # )
    # if backend == "sqlite":
    #     import session_db_sqlite as session_db
    # elif backend == "postgres":
    #     import session_db_postgres as session_db
    # else:
    #     st.warning("Please select a database backend to continue.")
    #     st.stop()
    # os.environ["SESSION_DB_BACKEND"] = backend
    # session_db.ensure_sessions_table()
    #
    # --- Default to PostgreSQL ---
    import session_db_postgres as session_db
    os.environ["SESSION_DB_BACKEND"] = "postgres"
    session_db.ensure_sessions_table()

    # WHY: System prompt is dynamically set based on the selected level, using Jinja2 templates for flexibility.
    if level == "Level I":
        st.session_state["system_prompt"] = render_jinja_prompt(LEVEL_1_PROMPT_JINJA, context) or "You are a translator and you will translate to level 1 Latin."
    else:
        st.session_state["system_prompt"] = render_jinja_prompt(LEVEL_2_PROMPT_JINJA, context) or "You are a Latin translator and you will translate to level 2 college Latin."
    # WHY: Save session button allows users to persist their work and recover it later.
    if st.button("Save Session"):
        # Only save serializable items from session state
        serializable_state = {k: v for k, v in st.session_state.items() if isinstance(v, (str, int, float, bool, list, dict, type(None)))}
        session_file = Path(__file__).parent / "sessions" / "session.json"
        session_file.parent.mkdir(exist_ok=True)
        with open(session_file, "w") as f:
            json.dump(serializable_state, f)
        st.success("Session saved!")
    st.markdown("---")
    st.caption("Model in use: gemini-2.5-pro")
    st.caption("Powered by Gemini")

# --- MAIN AREA ---
# WHY: The main area displays the chat interface, including chat history and the chat input box. This is the core user interaction zone.
st.header(":speech_balloon: pAIdagogue Chat")
chat_history = st.session_state.get("chat_history", "")
chat_html = ""
if chat_history:
    # WHY: Parse and render chat history as styled HTML blocks for user and system messages.
    lines = chat_history.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("User:"):
            user_msg = markdown2.markdown(line[5:].strip())
            chat_html += f"<div style='background-color:#e6f7ff; border-radius:8px; padding:8px; margin-bottom:4px;'><span style='font-weight:normal;'>🧑🏽 User</span> {user_msg}</div>"
            i += 1
        elif line.startswith("System:"):
            system_response = line[7:].strip()
            idx = i
            response_lines = [system_response]
            for j in range(idx+1, len(lines)):
                if lines[j].startswith("User:") or lines[j].startswith("System:"):
                    break
                response_lines.append(lines[j])
            full_response = "\n".join([l.strip() for l in response_lines if l.strip()])
            full_response_html = markdown2.markdown(full_response)
            # WHY: Replace markdown bullet points with HTML <ul><li> for better formatting.
            import re
            def bullets_to_html(md):
                lines = md.split('\n')
                in_list = False
                html_lines = []
                for l in lines:
                    if re.match(r'^\* ', l):
                        if not in_list:
                            html_lines.append('<ul style="margin:0 0 0 1.2em;">')
                            in_list = True
                        html_lines.append(f'<li>{l[2:].strip()}</li>')
                    else:
                        if in_list:
                            html_lines.append('</ul>')
                            in_list = False
                        html_lines.append(l)
                if in_list:
                    html_lines.append('</ul>')
                return '\n'.join(html_lines)
            full_response_html = bullets_to_html(full_response_html)
            chat_html += f"<div style='background-color:#f0f0f0; border-radius:8px; padding:8px; margin-bottom:4px;'><span style='font-weight:normal;'>♊ Gemini</span> {full_response_html}</div>"
            i += len(response_lines)
        else:
            i += 1
# WHY: Render the chat history in a scrollable, styled container for better UX.
st.markdown(
    f"""<div style='background:white; height:400px; overflow-y:scroll; padding:8px; border:1px solid #ddd; border-radius:8px; margin-bottom:32px;'>{chat_html}</div>""",
    unsafe_allow_html=True,
)

# Do NOT reset system_prompt anywhere else!

# Determine if the chat input should be enabled based on level selection
level = st.session_state.get("level_chatapi", "Select a level")
chat_enabled = level in ["Level I", "Level II"]

with st.form("chat_form", clear_on_submit=True):
    if not chat_enabled:
        st.warning("Please select a level (Level I or Level II) before entering a message.")
    user_input = st.text_input("Your message", key="user_input", disabled=not chat_enabled)
    submitted = st.form_submit_button("Send", disabled=not chat_enabled)
    if submitted and user_input.strip():
        # WHY: Add the user message to chat history and chat_messages for LLM context.
        chat_history = st.session_state.get("chat_history", "")
        chat_history += f"\nUser: {user_input}"
        st.session_state["chat_history"] = chat_history
        st.session_state["chat_history_display"] = chat_history

        # Add to chat_messages for LLM context
        if "chat_messages" not in st.session_state:
            st.session_state["chat_messages"] = []
        st.session_state["chat_messages"].append({"role": "user", "content": user_input})

        st.session_state["llm_ready"] = True
        st.rerun()

# After the form, if llm_ready is set, call the LLM and update display
if st.session_state.get("llm_ready", False):
    # WHY: Prepare messages for LLM call, including system prompt and chat history.
    chat_history = st.session_state.get("chat_history", "")
    system_prompt = st.session_state.get("system_prompt", "")
    messages = [{"role": "system", "content": system_prompt}] + [
        m for m in st.session_state.get("chat_messages", [])
    ]
    try:
        # WHY: Call the Gemini pipeline and append the assistant's response to chat history and chat_messages.
        response = asyncio.run(pipe.pipe({"model": selected_model, "messages": messages}, {}, lambda x: None, {}))
        chat_history += f"\nSystem: {response}"
        st.session_state["chat_history"] = chat_history
        st.session_state["chat_history_display"] = chat_history

        # Add assistant response to chat_messages for context
        st.session_state["chat_messages"].append({"role": "assistant", "content": response})

        st.session_state["llm_ready"] = False
        st.rerun()
    except Exception as e:
        st.session_state["llm_ready"] = False
        st.write(f"Error: {e}")

# Save session
# WHY: Save session button allows users to persist their work and recover it later.
if st.button("Save Session"):
    serializable_state = {k: v for k, v in st.session_state.items() if isinstance(v, (str, int, float, bool, list, dict, type(None)))}
    session_file = Path(__file__).parent / "sessions" / "session.json"
    session_file.parent.mkdir(exist_ok=True)
    with open(session_file, "w") as f:
        json.dump(serializable_state, f)
    st.write("Session saved.")
    print(f"[Streamlit] Session state after Save Session: {dict(st.session_state)}")