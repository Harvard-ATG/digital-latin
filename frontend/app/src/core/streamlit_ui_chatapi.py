import os
import sys
import json
import asyncio
import datetime
import html
import session_db_postgres as session_db
import logging
import sentry_sdk
import traceback
import re
import streamlit as st
from pathlib import Path
from flow_api_endpoint import call_flow_score_endpoint, convert_chat_messages_to_chat_history
from datetime import datetime
from jinja2 import Template

# Initialize Sentry for error tracking
sentry_sdk.init(
    dsn="https://175659c068864530742625044e39cd9b@o291188.ingest.us.sentry.io/4509640390803457",
    send_default_pii=True,
    traces_sample_rate=1.0, # Tracing captured
    environment="digital-latin-streamlit-ui-dev"
)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
stdout_handler.addFilter(lambda record: record.levelno < logging.ERROR)

stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.ERROR)

formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
stdout_handler.setFormatter(formatter)
stderr_handler.setFormatter(formatter)

logger.handlers = [stdout_handler, stderr_handler]

try:
    logger.debug("Imported session_db_postgres")
    os.environ["SESSION_DB_BACKEND"] = "postgres"
    session_db.ensure_sessions_table()
    logger.debug("Called ensure_sessions_table")
except Exception as e:
    logger.debug(f"Exception during DB setup: {e}")

SKIP_DB = os.getenv("SKIP_DB", "false").lower() == "true"

# --- AUTHENTICATION ---
def check_auth():
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    authenticated_users = {
        os.environ["AUTH_USER_1"]: os.environ["AUTH_PASSWORD_1"],
        os.environ["AUTH_USER_2"]: os.environ["AUTH_PASSWORD_2"],
        os.environ["AUTH_USER_3"]: os.environ["AUTH_PASSWORD_3"],
    }
    if st.button("Login"):
        if username in authenticated_users.keys() and password == authenticated_users[username]:
            st.session_state["authenticated"] = True
        else:
            st.error("Invalid username or password")

if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.title("Login")
    check_auth()
    st.stop()

if st.session_state.get("clear_chat_input", False):
    st.session_state["chat_input_text"] = ""
    st.session_state["clear_chat_input"] = False

# --- GLOBAL SESSION STATE INITIALIZATION & PENDING LOAD HANDLING ---

# Utility Functions
# --- Utility Functions ---
def pad_label(label, width=30):
    """Pad the label with spaces for sidebar alignment."""
    return label.ljust(width)

def human_readable_time(ts):
    """Convert ISO timestamp to a more readable format for display."""
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime('%b %d, %Y %I:%M %p')
    except Exception:
        return ts
    
# WHY: Streamlit reruns the script top-to-bottom on every user interaction. This block ensures that if a session is being loaded,
# its data is applied to session_state before any widgets are created, so the UI reflects the loaded session immediately.

# Initialize should_call_llm if it doesn't exist
if "should_call_llm" not in st.session_state:
    st.session_state.should_call_llm = False

# Before rendering the input area, set llm_busy flag
if "llm_busy" not in st.session_state:
    st.session_state.llm_busy = False

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

os.environ["SESSION_DB_BACKEND"] = "postgres"
session_db.ensure_sessions_table()

# --- SIDEBAR ---
# WHY: The sidebar provides navigation, settings, and session management. It is the main entry point for users to select models, levels, and manage their work.
with st.sidebar:
    # --- New Session Button at the Top of the Sidebar ---
    new_session_sidebar = st.button(
        "New Session",
        key="new_session_sidebar_btn",
        use_container_width=True,
        help="Start a new session. This will clear the chat and reset the level."
    )
    if new_session_sidebar:
        # If a session is active, record end_reason before clearing
        session_db_id = st.session_state.get("session_db_id")
        session_title = st.session_state.get("session_title", "Untitled Session")
        if session_db_id:
            session_db.save_session(session_title, dict(st.session_state), session_db_id=session_db_id, end_reason="new session started", skip_db=SKIP_DB)
        st.session_state.clear()
        st.session_state["authenticated"] = True
        st.rerun()
    # Style the sidebar New Session button to be dark grey with white text
    # st.markdown("""
    #     <style>
    #     div[data-testid="stSidebar"] button[kind="secondary"]#new_session_sidebar_btn {
    #         background-color: #333 !important;
    #         color: #fff !important;
    #         border-radius: 6px !important;
    #         font-weight: 600;
    #         margin-top: 0.5em;
    #         margin-bottom: 0.5em;
    #     }
    #     </style>
    # """, unsafe_allow_html=True)

    st.title("pAIdagogue Chat")
    st.markdown(
        "Simplify authentic Latin passages for your students using AI.  \n\n"
        "Choose a simplification level to match your students' experience:  \n"
        "* **Level 1** for first-year.  \n"
        "* **Level 2** for second-year Latin.  \n\n"
    )
    st.markdown("---")
    st.header("Settings")
    # WHY: Allowed models are set via environment variable for flexibility across deployments.
    allowed_models_env = os.getenv("GOOGLE_ALLOWED_MODELS", "gemini-2.5-pro")
    allowed_models = [m.strip() for m in allowed_models_env.split(",") if m.strip()]

    # WHY: Ensure model and level are always initialized, even after session clears or loads.
    if "selected_model_chatapi" not in st.session_state or st.session_state.selected_model_chatapi not in allowed_models:
        st.session_state.selected_model_chatapi = allowed_models[0] if allowed_models else "gemini-2.5-pro"
    if "level_chatapi" not in st.session_state:
        st.session_state.level_chatapi = "Select a level"

    # WHY: These selectboxes are bound to session_state so that loading a session or changing a setting updates the UI and logic everywhere.
    # Removed the selectbox for model selection from the sidebar UI.
    # Level selection: no default, starts with placeholder, only enabled if not already selected for this session.
    level_options = ["Select a level", "Level 1", "Level 2"]
    level_selected = st.session_state.get("level_selected", False)
    current_level = st.session_state.get("level_chatapi", "Select a level")
    level_disabled = level_selected and current_level in ["Level 1", "Level 2"]
    level = st.selectbox(
        "Select Level",
        level_options,
        index=level_options.index(current_level) if current_level in level_options else 0,
        key="level_chatapi",
        disabled=level_disabled
    )
    # Only allow selection if not disabled and a real level is chosen
    if level_selected is False and level in ["Level 1", "Level 2"]:
        st.session_state["level_selected"] = True

        # Save a new session immediately when level is selected
        session_title = st.session_state.get("session_title", "Untitled Session")
        session_data = dict(st.session_state)  # Capture current session state
        session_data["messages"] = st.session_state.get("chat_messages", [])
        session_db_id = session_db.save_session(session_title, session_data=session_data)
        st.session_state["session_db_id"] = session_db_id
        st.rerun()

    # Show caption if a real level is selected and selector is disabled
    if (
        st.session_state.get("level_selected", False)
        and st.session_state.get("level_chatapi") in ["Level 1", "Level 2"]
    ):
        st.caption("To reset or select another level, start a new session.")

    # TODO: Add a feature toggle for Past session management, allowing users to choose between file-based or DB-based sessions.
    # --- BEGIN: Standard (non-DB) session sidebar code (TEMPORARILY DISABLED) ---
    # st.markdown("---")
    # st.subheader("Past Sessions (File)")
    # for session_file in Path("sessions").glob("*.json"):
    #     session_name = session_file.stem
    #     if st.button(session_name, key=f"session_file_{session_name}"):
    #         with open(session_file) as f:
    #             past_session_data = json.load(f)
    #         for k, v in past_session_data.items():
    #             st.session_state[k] = v
    #         st.success(f"Loaded session: {session_name}")
    # --- END: Standard (non-DB) session sidebar code ---

    # --- BEGIN: DB-validated session sidebar code (INACTIVE) ---
    # st.markdown('---')
    # st.subheader('Past Sessions')
    # # WHY: List all saved sessions from the PostgreSQL DB for display in the sidebar.
    # for sid, name, ts in session_db.list_sessions():
    #     padded_name = pad_label(name, width=28)
    #     button_label = f"{padded_name}\n[{human_readable_time(ts)}]"
    #     cols = st.columns([0.85, 0.15])
    #     session_btn_key = f'session_chatapi_{sid}_btn'
    #     delete_btn_key = f'delete_session_{sid}_btn'
    #     with cols[0]:
    #         if st.button(button_label, key=session_btn_key, help=human_readable_time(ts)):
    #             session_db.load_session(sid) # Call the modified load_session
    #     with cols[1]:
    #         delete_clicked = st.button("🗑️", key=delete_btn_key, help="Delete Session")
    #         if delete_clicked:
    #             session_db.delete_session(sid)
    # --- END: DB-validated session sidebar code ---


    session_title = st.session_state.get("session_title", None)
    show_save_button = (
        session_title
        and st.session_state.get("chat_messages")
        and not st.session_state.get("_rerun_from_load", False) # Check this flag
    )

    # TODO: Add feature toggle: This block enables the save session button functionality in sidebar.
    # if show_save_button:
    #     print("[DEBUG] if show_save_button")
    #     save_clicked = st.button('Save Current Session (Chat API)')
    #     if save_clicked:
    #         print("[DEBUG] if save_clicked")
    #         session_db.save_session(session_title)
    #         st.success('Session saved!')
    # --- END: Save Current Session Button ---

    # Sidebar footer with model information and powered by Gemini.
    st.markdown("---")
    st.caption("Powered by Gemini")
    selected_model = "gemini-2.5-pro"
    st.session_state["selected_model_chatapi"] = selected_model
    st.caption(f"Model: {selected_model}")

# --- LLM CALL TRIGGER BLOCK: MUST BE BEFORE ANY UI RENDERING ---
if st.session_state.get("llm_busy", False) and st.session_state.get("should_call_llm", False):
    st.session_state.should_call_llm = False  # Prevent duplicate LLM calls on rerun
    try:
        with st.spinner("Assistant is thinking..."):
            selected_model = st.session_state.get("selected_model_chatapi", "gemini-2.5-pro")
            messages = [m for m in st.session_state["chat_messages"]]

            logger.debug(f"Attempt to call /score endpoint with model: {selected_model}, level: {current_level}")
            response_content = call_flow_score_endpoint(
                chat_history=convert_chat_messages_to_chat_history(messages),
                level=current_level,
                llm_model_id=selected_model,
            )
            logger.debug(f"Response from /score endpoint: {response_content}")

            # No duplicate check for the last assistant message - Check if the last message is an assistant
            # response with the same content
            if not (
                st.session_state["chat_messages"]
                and st.session_state["chat_messages"][-1]["role"] == "assistant"
                and st.session_state["chat_messages"][-1]["content"].strip() == response_content["content"].strip()
            ):
                st.session_state["chat_messages"].append(response_content)
                session_db_id = st.session_state.get("session_db_id")
                if session_db_id:
                    session_db.log_message(session_db_id, "assistant", response_content["content"])
            else:
                # Session DB logging is not needed if the last message is a duplicate
                logger.debug("Duplicate assistant message detected, not logging to session DB.")
                pass
    except Exception as e:
        error_info = f"Error: {e}\nRaw object type: {type(e.__context__ if e.__context__ else 'Unknown')}\nRaw object details: {response_content if 'response_content' in locals() else 'Not available'}"
        st.session_state["chat_messages"].append({"role": "assistant", "content": error_info})
    finally:
        st.session_state.llm_busy = False  # Not busy after response
        st.rerun()  # Rerun to display the new assistant message and re-enable the button
    st.stop()  # Prevents any further UI rendering in this run

# --- MAIN AREA ---
# The main area displays the chat interface, including chat history and the chat input box.
# This is the core user interaction zone.

st.header(":speech_balloon: pAIdagogue Chat")
if "chat_messages" not in st.session_state:
    logger.debug("if 'chat_messages' not in st.session_state")
    st.session_state["chat_messages"] = []

# --- CUSTOM CSS STYLING ---
# Inject custom CSS for improved UI/UX in the Main Area, including font and chat input styling.

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined');
    .material-symbols-outlined {
      font-family: 'Material Symbols Outlined';
      font-variation-settings:
        'FILL' 0,
        'wght' 400,
        'GRAD' 0,
        'opsz' 20;
      font-size: 18px;
      vertical-align: middle;
      color: #1f1f1f;
      user-select: none;
    }
    </style>
""", unsafe_allow_html=True)

# Additional CSS to remove grey padding/margins from chat input area
st.markdown("""
<style>
section[data-testid="stChatInput"] {
    background: #e3f2fd !important;
    border-radius: 10px !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}
section[data-testid="stChatInput"] div[role="textbox"] {
    background: #e3f2fd !important;
    color: #17416b !important;
    border: none !important;
    box-shadow: none !important;
    padding: 20px 24px !important;
    margin: 0 !important;
    font-size: 2em !important;
    min-height: 8em !important;
    height: 8em !important;
    line-height: 1.5 !important;
}
section[data-testid="stChatInput"] label {
    background: #e3f2fd !important;
    color: #17416b !important;
    font-size: 1.2em !important;
}
section[data-testid="stChatInput"] textarea,
section[data-testid="stChatInput"] input {
    font-size: 2em !important;
    min-height: 3em !important;
    height: 3em !important;
    line-height: 1.5 !important;
    padding: 20px 24px !important;
    resize: vertical !important;
}
<!-- Start Style for chat messages -->
div.st-emotion-cache-1fee4w7:has([data-testid="stChatMessageAvatarUser"]) {
    background: #fff !important;
}
div.st-emotion-cache-1iitqle:has([data-testid="stChatMessageAvatarAssistant"]) {
    background: #fffde7 !important;
}
div.st-emotion-cache-1flajlm:has([data-testid="stChatMessageAvatarAssistant"]) {
    background: #fffde7 !important;  /* Light yellow background */
    border-radius: 12px !important;
}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: #fff !important;  /* White background for user messages */
    border-radius: 12px !important;
}
<!-- Style for assistant messages with light yellow background -->
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background: #fffde7 !important;  /* Light yellow background */
}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) div[data-testid="stChatMessageContent"] {
    background: #fffde7 !important;  /* Light yellow background for assistant bubble */
    border-radius: 12px !important;
    padding: 16px 18px !important;
    margin-bottom: 0.5em !important;
}
<!-- Style - formats bullets -->
.custom-section-title {
    margin-bottom: 0.2em !important;
}
.custom-bullet-list {
    margin-top: 0 !important;
}
<!-- End Style for chat messages -->
</style>  
""", unsafe_allow_html=True)

# --- END CUSTOM CSS STYLING --- #


# --- RENDER CHAT HISTORY --- #
# Chat history is rendered here, showing all messages in the session.

# Session title if available, to help users keep track of their current topic.
session_title = st.session_state.get("session_title", None)
if session_title:
    st.markdown(f"<div style='font-size:1.1em; color:#555; margin-bottom:0.5em;'><b>Session Topic:</b> {session_title}</div>", unsafe_allow_html=True)

# Deduplicate chat messages to avoid repeated entries after reruns or session loads.
seen = set()
deduped = []
for msg in st.session_state["chat_messages"]:
    role = msg.get("role")
    content = msg.get("content")
    # Safely convert content to a string for hashing
    if isinstance(content, dict):
        content_str = json.dumps(content, sort_keys=True)
    else:
        content_str = str(content)
    msg_id = (role, content_str)
    if msg_id not in seen:
        seen.add(msg_id)
        deduped.append(msg)
st.session_state["chat_messages"] = deduped  # Always update to ensure deduplication

# Renders chat history using st.chat_message for a native chat UI experience.
logger.debug(f"[Streamlit] Rendering chat history. Total messages: {len(st.session_state.get('chat_messages', []))}")
for idx, msg in enumerate(st.session_state["chat_messages"]):
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(
                f"<div style='background:#e3f2fd; color:#17416b; border-radius:8px; padding:16px 18px; margin-bottom:8px; font-size:1.05em; width:100%; max-width:648px; box-sizing:border-box; word-break:break-word; overflow-wrap:break-word;'>{html.escape(msg['content'])}</div>",
                unsafe_allow_html=True
            )
        elif msg["role"] == "assistant":
            def style_code(text):
                # Replace `code` with styled span
                # Color of the assistant's response code is set to #8c3f1a (dark red)
                return re.sub(r'`([^`]+)`', r"<span style='color:#8c3f1a; font-weight:400;'>\1</span>", text)
            styled_content = style_code(msg['content'].replace('\n', '  \n'))
            st.markdown(styled_content, unsafe_allow_html=True)

# --- RESTORE THE CHAT INPUT AREA ---
# The chat input box is always shown at the bottom, unless a level is not selected.
# This must be after the chat history rendering, and before the LLM call trigger block
# to ensure the chat input is always available for user interaction.

level = st.session_state.get("level_chatapi", "Select a level")
chat_enabled = level in ["Level 1", "Level 2"]

# If no level is selected, show a warning message to guide the user.
# This is to ensure users know they need to select a level before entering messages.
if not chat_enabled:
    logger.debug("if not chat_enabled")
    st.warning("Select a level (Level 1 or Level 2) in the **left sidebar** to enter a message.")

# --- Use a text area for chat input instead of st.chat_input ---
if "chat_input_text" not in st.session_state:
    logger.debug("if 'chat_input_text' not in st.session_state")
    st.session_state["chat_input_text"] = ""

if chat_enabled:
    # --- MOVE THE SPINNER/CAPTION HERE, RIGHT BEFORE THE INPUT ---
    # This ensures the caption is always right above the input, not above the chat history.
    # This may not be necessary if the spinner is only shown during LLM calls.
    if st.session_state.get("llm_busy", False):
        st.caption("Thinking...")

    chat_col1, chat_col2 = st.columns([12, 1])
    with chat_col1:
        user_text = st.text_area(
            "Your message",
            value=st.session_state["chat_input_text"],
            key="chat_input_text",
            height=250,
            label_visibility="collapsed",
            placeholder="Type your message here...",
            disabled=not chat_enabled,
        )
    with chat_col2:
        send_clicked = st.button(
            "➤",
            key="send_chat_btn",
            help="Send message",
            use_container_width=True,
            disabled=st.session_state.get("llm_busy", False) # Disable while LLM is busy
        )

    # Sends to LLM on ➤ button click or if Enter is pressed and only one line (simulate send on enter)
    if send_clicked and user_text.strip():
        logger.debug("if send_clicked and user_text.strip()")
        st.session_state["chat_messages"].append({"role": "user", "content": user_text})
        session_db_id = st.session_state.get("session_db_id")
        if session_db_id:
            session_db.log_message(session_db_id, "user", user_text, skip_db=SKIP_DB)
        st.session_state["clear_chat_input"] = True
        st.session_state["pending_llm"] = True  # New flag to trigger LLM on next rerun
        st.rerun()
    # Optionally, you can add a note for the user
    # TODO: Remove this caption if not needed
    # if not st.session_state.get("llm_busy", False):
    st.caption("Press the ➤ button to send your message.")
    
# --- Final Rerun Handling for Session Loading (after all other logic) ---
# After loading a session, clear the rerun flag so the UI is stable and ready for user input.
# This ensures a final clean rerun after _pending_session_load_data has been processed
# This flag is set by the initial "_pending_session_load_data" block now.
if st.session_state.get("_rerun_from_load", False):
    logger.debug("if _rerun_from_load")
    del st.session_state["_rerun_from_load"]
    # No st.rerun() here, as this means we're done with the load sequence.
    # The next action will be user input or Streamlit's idle rerun.

# --- At the very top of the script, before any UI rendering ---
if st.session_state.get("pending_llm", False) and not st.session_state.get("llm_busy", False):
    st.session_state["llm_busy"] = True
    st.session_state["should_call_llm"] = True
    st.session_state["pending_llm"] = False
    st.rerun()