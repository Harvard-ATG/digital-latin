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
from PIL import Image

# Initialize Sentry for error tracking
sentry_sdk.init(
    dsn="https://175659c068864530742625044e39cd9b@o291188.ingest.us.sentry.io/4509640390803457",
    send_default_pii=True,
    traces_sample_rate=1.0, # Tracing captured
    environment="digital-latin-streamlit-ui-dev"
)

im = Image.open("/app/src/assets/images/gear_robot_owl_face_chatgptedu_generated_2025-08-15.png")
st.set_page_config(
    page_title="pAIdagogue Chat",
    page_icon=im,
    layout="wide",
    initial_sidebar_state="expanded",
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

# Define screen reader accessibility CSS early so it's available immediately
st.markdown("""
<style>
/* Screen reader only text - visually hidden but accessible */
.sr-only {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    padding: 0 !important;
    margin: -1px !important;
    overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important;
    white-space: nowrap !important;
    border: 0 !important;
}

/* Hide the header action elements (e.g. "New Session" button) */
[data-testid='stHeaderActionElements'] {
    display: none;
}

/* Hide anchor links next to headers */
h1 a, h2 a, h3 a, h4 a, h5 a, h6 a {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
.stMarkdown h1 a, .stMarkdown h2 a, .stMarkdown h3 a, .stMarkdown h4 a, .stMarkdown h5 a, .stMarkdown h6 a {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
/* More specific targeting for main content headers */
div[data-testid="stHeader"] h1 a, 
div[data-testid="stHeader"] h2 a,
section[data-testid="stMain"] h1 a,
section[data-testid="stMain"] h2 a,
section[data-testid="stSidebar"] h1 a,
section[data-testid="stSidebar"] h2 a {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
/* Hide any anchor elements that might be empty or causing form issues */
a[href="#"]:empty, a:empty {
    display: none !important;
    visibility: hidden !important;
}
/* Nuclear option - hide ALL anchor tags in headers regardless of nesting */
* h1 * a, * h2 * a, * h3 * a, * h4 * a, * h5 * a, * h6 * a {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
            
/* Reduce the header above the new session button */
div.st-emotion-cache-10p9htt:has(div[data-testid="stSidebarHeader"]) p {
    height: 60px !important;
}

div.st-emotion-cache-479nsk:has(div[data-testid="stMarkdownContainer"]) p {
    font-size: 2rem !important;
}

/* Target the sidebar section for accessibility enhancements */
section[data-testid="stSidebar"] {
    position: relative;
}

/* Alternative targeting for the sidebar toggle icon */
section[data-testid="stSidebar"] span[data-testid="stIconMaterial"]:after {
    content: "double_arrow_left_close_sidebar_button";
    position: absolute;
    left: -10000px;
    top: 0;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
}
</style>
""", unsafe_allow_html=True)

# Custom CSS to hide the kebab menu and footer
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stAppHeader {display: none;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Custom CSS to hide the deploy button
hide_deploy_button = """
<style>
.stDeployButton {
    display: none;
}
.stAppDeployButton {
    display: none;
}
</style>
"""
st.markdown(hide_deploy_button, unsafe_allow_html=True)

try:
    logger.debug("Imported session_db_postgres")
    os.environ["SESSION_DB_BACKEND"] = "postgres"
    session_db.ensure_sessions_table()
    logger.debug("Called ensure_sessions_table")
except Exception as e:
    logger.debug(f"Exception during DB setup: {e}")

SKIP_DB = os.getenv("SKIP_DB", "false").lower() == "true"

# --- FOCUS COMPONENT REGISTRY ---
def get_focus_components():
    """
    Define all interactive components with explicit focus order and accessibility info.
    Lower numbers = earlier in tab order (1, 2, 3, etc.)
    """
    # Check if we're on the login screen
    if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
        # LOGIN SCREEN COMPONENTS (Order 1-4 to match CSS tab-index)
        return [
            {
                "id": "username_input",
                "order": 1,
                "type": "text_input",
                "section": "login",
                "label": "Username",
                "help": "Enter your username to access the application",
                "enabled": True,
                "visible": True,
                "focus_text": "Username field - enter your username to log in"
            },
            {
                "id": "password_input", 
                "order": 2,
                "type": "text_input",
                "section": "login",
                "label": "Password",
                "help": "Enter your password to access the application",
                "enabled": True,
                "visible": True,
                "focus_text": "Password field - enter your password to log in"
            },
            {
                "id": "show_password_button",
                "order": 3,
                "type": "button",
                "section": "login",
                "label": "Show/Hide Password",
                "help": "Toggle password visibility",
                "enabled": True,
                "visible": True,
                "focus_text": "Show password button - press to reveal or hide your password"
            },
            {
                "id": "login_button",
                "order": 4,
                "type": "button",
                "section": "login",
                "label": "Login",
                "help": "Click to log in with your credentials",
                "enabled": True,
                "visible": True,
                "focus_text": "Login button - press to authenticate and access the application"
            }
        ]
    
    # MAIN APPLICATION COMPONENTS
    llm_busy = st.session_state.get("llm_busy", False)
    chat_enabled = st.session_state.get("level_chatapi") in ["Level 1", "Level 2"]
    level_selected = st.session_state.get("level_selected", False)
    current_level = st.session_state.get("level_chatapi")
    
    components = []
    
    # SIDEBAR COMPONENTS (Order 1-10)
    components.append({
        "id": "new_session_sidebar_btn",
        "order": 1,
        "type": "button",
        "section": "sidebar",
        "label": "New Session",
        "help": "Start a new session. This will clear the chat and reset the level.",
        "enabled": True,
        "visible": True,
        "focus_text": "New Session button - press to start a new chat session"
    })
    
    components.append({
        "id": "level_chatapi",
        "order": 2,
        "type": "radio",
        "section": "sidebar",
        "label": "Select Level",
        "help": "Choose simplification level for Latin passages",
        "enabled": not (level_selected and current_level in ["Level 1", "Level 2"] and st.session_state.get("chat_messages")),
        "visible": True,
        "focus_text": ("Level selector radio buttons - choose Level 1 for first-year or Level 2 for second-year Latin students"
                        if not (level_selected and current_level in ["Level 1", "Level 2"] and st.session_state.get("chat_messages"))
                        else "Level selector radio buttons - level is locked for this session")
    })

    # MAIN CHAT COMPONENTS (Order 11-20)
    if chat_enabled:
        if not llm_busy:
            # Normal input mode
            components.append({
                "id": "chat_input_text",
                "order": 11,
                "type": "text_area",
                "section": "main",
                "label": "Your message",
                "help": "Type your Latin passage or question here",
                "enabled": chat_enabled,
                "visible": True,
                "focus_text": "Message input area - type your Latin passage or question here"
            })
            
            components.append({
                "id": "send_chat_btn",
        "order": 12,
                "type": "button",
                "section": "main", 
                "label": "➤",
                "help": "Send message button",
                "enabled": chat_enabled,
                "visible": True,
                "focus_text": "Send message button - press to send your message to the AI assistant"
            })
        else:
            # LLM busy mode - only stop button
            components.append({
                "id": "stop_chat_btn",
                "order": 11,
                "type": "button",
                "section": "main",
                "label": "⏹ Stop",
                "help": "Stop assistant",
                "enabled": True,
                "visible": True,
                "focus_text": "Stop button - press to cancel the AI assistant's current response"
            })
    
    # Sort by order and return
    return sorted(components, key=lambda x: x["order"])

def get_component_help_text(component_id):
    """Get the appropriate help text for a component by ID"""
    components = get_focus_components()
    for comp in components:
        if comp["id"] == component_id:
            return comp["help"]
    return ""

def get_component_focus_text(component_id):
    """Get the focus/accessibility text for a component by ID"""
    components = get_focus_components()
    for comp in components:
        if comp["id"] == component_id:
            return comp["focus_text"]
    return ""

def log_focus_order():
    """Debug function to log the current focus order"""
    components = get_focus_components()
    logger.debug("[FOCUS ORDER] Current component order:")
    for comp in components:
        if comp["visible"] and comp["enabled"]:
            logger.debug(f"  {comp['order']}: {comp['id']} ({comp['type']}) - {comp['focus_text']}")

# --- AUTHENTICATION ---
def check_auth():
    # Add CSS to hide show password buttons
    st.markdown("""
    <style>
    /* Hide Streamlit's built-in show password button */
    [title="Show password text"] {
        display: none;
    }
    /* Hide custom show password button to prevent focus cycling */
    .show-password-btn {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)
    
    username = st.text_input(
        "Username",
        key="username_input", 
        help=get_component_help_text("username_input"),
        placeholder="Enter your username"
    )
    
    password = st.text_input(
        "Password", 
        type="password",
        key="password_input",
        help=get_component_help_text("password_input"),
        placeholder="Enter your password"
    )
    
    authenticated_users = {
        os.environ["AUTH_USER_1"]: os.environ["AUTH_PASSWORD_1"],
        os.environ["AUTH_USER_2"]: os.environ["AUTH_PASSWORD_2"],
        os.environ["AUTH_USER_3"]: os.environ["AUTH_PASSWORD_3"],
    }
    
    login_clicked = st.button(
        "Login",
        key="login_button",
        help=get_component_help_text("login_button"),
    )
    
    if login_clicked:
        if username in authenticated_users.keys() and password == authenticated_users[username]:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Invalid username or password")


if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    # The instructions for the form
    instructions_html = """
    <div id="login-instructions" class="sr-only">
        pAIdagogue Login Form Instructions: Please enter your credentials to access the Latin text simplification tool.
        This form has two fields, Username and Password, and a Login button.
        Use the Tab key to navigate between fields.
    </div>
    """
    st.markdown(instructions_html, unsafe_allow_html=True)
    st.title("pAIdagogue Login")
    st.markdown("Please enter your credentials to access the Latin text simplification tool.")

    # Add CSS for login screen focus order and all accessibility styles BEFORE any form elements
    st.markdown("""
    <style>
    /* NOTE: The following original CSS attempts to control tab order using `tabindex` inside CSS rules. */
    /* This does NOT work because tabindex must be an HTML attribute, not a CSS property. */
    /* Keeping these here commented for historical/reference purposes. */
    /*
    input[data-testid*="username_input"] { tabindex: 1 !important; }
    input[data-testid*="password_input"] { tabindex: 2 !important; }
    button[aria-label="Show password text"] { tabindex: 3 !important; }
    button[aria-label*="password"] { tabindex: 3 !important; }
    div[data-testid*="password_input"] ~ div button { tabindex: 3 !important; }
    div[data-testid*="password_input"] button { tabindex: 3 !important; }
    div[data-testid="stElementContainer"].st-key-login_button button[data-testid="stBaseButton-secondary"] { tabindex: 4 !important; }
    button[data-testid="stBaseButton-secondary"]:has(div[data-testid="stMarkdownContainer"] p:contains("Login")) { tabindex: 4 !important; }

    / * CSS-only fallback that attempted to hide duplicate buttons (kept commented) * /
    / *
    section[data-testid="stMain"] div[data-testid="stElementContainer"] button[data-testid="stBaseButton-secondary"] {
        display: none !important;
    }
    section[data-testid="stMain"] div[data-testid="stElementContainer"].st-key-login_button button[data-testid="stBaseButton-secondary"] {
        display: inline-flex !important;
    }
    section[data-testid="stMain"] button[aria-label*="password"],
    section[data-testid="stMain"] div[data-testid*="password_input"] button {
        display: inline-flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        pointer-events: auto !important;
    }
    */

    /* Active styles (non-tabindex related) */
    *:focus { outline: 3px solid #007acc !important; outline-offset: 2px !important; }
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a { display: none !important; }
    .stMarkdown h1 a, .stMarkdown h2 a, .stMarkdown h3 a { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

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

# Initialize http_call_in_progress flag to track actual HTTP calls
if "http_call_in_progress" not in st.session_state:
    st.session_state.http_call_in_progress = False

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
# Inject custom CSS to hide the collapse button
st.markdown("""
<style>
/* This CSS targets the "collapse sidebar" button by its data-testid attribute and hides it */
[data-testid="stSidebarCollapseButton"] {
    display: none
}
</style>
""", unsafe_allow_html=True)
with st.sidebar:
    sidebar_instructions_2_html = """
    <div id="sidebar-instructions" class="sr-only">
        pAIdagogue Chat Instructions: 
        PAidagogue Chat is a Latin text simplification tool designed to help instructors to simplify authentic Latin passages for their students using AI.
        To begin using the tool, select a level 1 or level 2 in the left sidebar to enter a latin passage. 
        This sidebar contains navigation and settings. First is the New Session button to start fresh, then level selection (Level 1 for first-year or Level 2 for second-year Latin students).
        Use the Tab key to navigate between controls.
    </div>
        """
    st.markdown(sidebar_instructions_2_html, unsafe_allow_html=True)
    # The instructions for the sidebar

    # --- New Session Button at the Top of the Sidebar ---
    new_session_sidebar = st.button(
        "New Session",
        key="new_session_sidebar_btn",
        use_container_width=True,
        help=get_component_help_text("new_session_sidebar_btn")
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
    # Style the sidebar New Session button to be dark grey with white text and custom height
    st.markdown("""
        <style>
        /* Style the New Session button using the outer HTML structure */
        div[data-testid="stTooltipHoverTarget"] button[data-testid="stBaseButton-secondary"] {
            /* background-color: #8C8C8C !important; */
            border: 2px rgba(49, 51, 63, 0.2) solid !important;
        }
        
        /* Target the tooltip hover target div that controls the actual button height */
        section[data-testid="stSidebar"] div[data-testid="stTooltipHoverTarget"] {
            height: 60px !important;
            min-height: 60px !important;
            max-height: 60px !important;
            color: #000000 !important; /* Ensure text color is black */
        }
                
        /* Reduce the header above the new session button */
        section[data-testid="stSidebar"] div[data-testid="stSidebarContent"] div[data-testid="stSidebarHeader"] {
            height: 1.2rem !important;
        }  
        
        /* Style the New Session button text size using :has() selector */
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] div[data-testid="stMarkdownContainer"] p {
            font-size: 1.2rem !important;
            color: #000000 !important; /* Ensure text color is black */
            font-weight: 600 !important; /* More Bold */
        }
        /* Style the Level captions
        section[data-testid="stRadio"] div[data-testid="stCaptionContainer"] p {
            color: #000000 !important; /* Ensure text color is black */
        }
                             
        </style>
    """, unsafe_allow_html=True)

    st.title("pAIdagogue Chat")
    st.write(
        "Simplify authentic Latin passages for your students using AI.  \n\n"
        "Choose a simplification level to match your students' experience:  \n"
        "* **Level 1** for first-year.  \n"
        "* **Level 2** for second-year Latin.  \n\n"
    )
    st.write("---")
    st.header("Settings")
    # WHY: Allowed models are set via environment variable for flexibility across deployments.
    allowed_models_env = os.getenv("GOOGLE_ALLOWED_MODELS", "gemini-2.5-pro")
    allowed_models = [m.strip() for m in allowed_models_env.split(",") if m.strip()]

    # WHY: Ensure model and level are always initialized, even after session clears or loads.
    if "selected_model_chatapi" not in st.session_state or st.session_state.selected_model_chatapi not in allowed_models:
        st.session_state.selected_model_chatapi = allowed_models[0] if allowed_models else "gemini-2.5-pro"
    if "level_chatapi" not in st.session_state:
        st.session_state.level_chatapi = None

    # WHY: These form components are bound to session_state so that loading a session or changing a setting updates the UI and logic everywhere.
    # Level selection form: Allow changes until user actually starts chatting
    LEVEL_OPTIONS = ["Level 1", "Level 2"]
    level_selected = st.session_state.get("level_selected", False)
    current_level = st.session_state.get("level_chatapi")
    
    # Only disable level selection if there are chat messages (user has started chatting)
    level_disabled = (level_selected and current_level in ["Level 1", "Level 2"] and 
                     bool(st.session_state.get("chat_messages")))
    
    # Always show radio buttons, disable when level is locked by chat messages
    selected_level = st.radio(
        "Select Level",
        LEVEL_OPTIONS,
        key="level_chatapi",           # direct session state binding
        # index=LEVEL_OPTIONS.index(current_level) if current_level in LEVEL_OPTIONS else None,
        captions=["Choose Level 1 for first-year Latin", "Choose Level 2 for second-year Latin"],
        disabled=level_disabled,
        horizontal=False
    )
    
    # Show caption if level is locked due to chat messages
    if (st.session_state.get("chat_messages") and 
        st.session_state.get("level_chatapi") in ["Level 1", "Level 2"]):
        st.caption("To reset or select another level, start a new session.")

    # Create session and lock level when user sends first message
    current_level = st.session_state.get("level_chatapi")
    if (current_level and current_level in ["Level 1", "Level 2"] and 
          st.session_state.get("chat_messages") and 
          not st.session_state.get("session_db_id")):
        # Save session and mark level as selected when user has messages
        st.session_state["level_selected"] = True
        session_title = st.session_state.get("session_title", "Untitled Session")
        session_data = dict(st.session_state)  # Capture current session state
        session_data["messages"] = st.session_state.get("chat_messages", [])
        session_db_id = session_db.save_session(session_title, session_data=session_data)
        st.session_state["session_db_id"] = session_db_id
        st.rerun()

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
    st.markdown("<p style='color: black; font-size: 0.75em; opacity: 0.6;'>Powered by Gemini</p>", unsafe_allow_html=True)
    selected_model = "gemini-2.5-pro"
    st.session_state["selected_model_chatapi"] = selected_model
    st.markdown(f"<p style='color: black; font-size: 0.75em; opacity: 0.6;'>Model: {selected_model}</p>", unsafe_allow_html=True)

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
/* Stop button styling */
button[data-testid="baseButton-secondary"]:has-text("⏹") {
    background-color: #ff4444 !important;
    color: white !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
}
button[data-testid="baseButton-secondary"]:has-text("⏹"):hover {
    background-color: #cc3333 !important;
}
/* Explicit tab order control - COMMENTED OUT */
/*
button[data-testid*="new_session_sidebar_btn"] { tab-index: 1 !important; }
div[data-testid*="level_chatapi"] div[role="radiogroup"] { tab-index: 2 !important; }

textarea[data-testid*="chat_input_text"] { tab-index: 11 !important; }
button[data-testid*="send_chat_btn"] { tab-index: 12 !important; }
button[data-testid*="stop_chat_btn"] { tab-index: 11 !important; }
*/
/* Focus indicators */
*:focus {
    outline: 3px solid #007acc !important;
    outline-offset: 2px !important;
}
/* Style info alerts to have black text instead of default blue/gold */
div[data-testid="stAlert"] div[data-testid="stMarkdownContainer"] p {
    color: black !important;
}
/* Style caption text to be larger and black */
div.st-emotion-cache-1fc0ges:has(div[data-testid="stCaptionContainer"]) p {
    font-size: 1.2em !important;
    color: black !important;
    font-weight: 500 !important;
}
            
/* Style caption text to be larger and black */
div.st-emotion-cache-1vo6xi6:has(div[data-testid="stCaptionContainer"]) p {
    font-size: 0.875em !important;
    color: black !important;
}
             
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
                # Color of the assistant's response code is set to black
                return re.sub(r'`([^`]+)`', r"<span style='color:#000000; font-weight:400;'>\1</span>", text)
            styled_content = style_code(msg['content'].replace('\n', '  \n'))
            st.markdown(styled_content, unsafe_allow_html=True)

# --- RESTORE THE CHAT INPUT AREA ---
# The chat input box is always shown at the bottom, unless a level is not selected.
# This must be after the chat history rendering, and before the LLM call trigger block
# to ensure the chat input is always available for user interaction.

level = st.session_state.get("level_chatapi")
chat_enabled = level in ["Level 1", "Level 2"]

# If no level is selected, show an info message to guide the user.
# This is to ensure users know they need to select a level before entering messages.
if not chat_enabled:
    logger.debug("if not chat_enabled")
    st.info("Select a level (Level 1 or Level 2) in the **left sidebar** to enter a message.")

# --- Use a text area for chat input instead of st.chat_input ---
if "chat_input_text" not in st.session_state:
    logger.debug("if 'chat_input_text' not in st.session_state")
    st.session_state["chat_input_text"] = ""

if chat_enabled:
    # --- MOVE THE SPINNER/CAPTION HERE, RIGHT BEFORE THE INPUT ---
    # This ensures the caption is al sways right above the input, not above the chat history.
    # This may not be necessary if the spinner is only shown during LLM calls.
    if st.session_state.get("llm_busy", False):
        # Show different messages based on whether request was cancelled
        if st.session_state.get("llm_cancelled", False):
            st.caption("Stopping...")
        else:
            st.caption("Thinking...")
        #####
        # Display that Assistant is busy and show stop button
        chat_col1, chat_col2 = st.columns([12, 1])
        with chat_col1:
            # Show different message based on cancellation state
            if st.session_state.get("llm_cancelled", False):
                message_text = "⏹ Stopping. Please wait..."
                bg_color = "#ffe6e6"  # Light red background for stopping
                text_color = "#cc3333"  # Red text for stopping
            else:
                message_text = "Assistant is thinking. Please wait..."
                bg_color = "#f0f0f0"  # Grey background for thinking
                text_color = "#000000"   # Black text for thinking

            # Show a non-editable message box instead of text area
            if st.session_state.get("llm_cancelled", False):
                # Just show the stopping message without spinner
                st.markdown(f"""
                <div style='
                    background-color: {bg_color};
                    color: {text_color};
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    padding: 20px 24px;
                    height: 250px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 1.2em;
                    font-weight: 500;
                    text-align: center;
                    margin-bottom: 1rem;
                '>
                    {message_text}
                </div>
                """, unsafe_allow_html=True)
            else:
                # Show thinking message with spinner
                st.markdown(f"""
                <style>
                @keyframes spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
                .thinking-spinner {{
                    margin-right: 12px;
                    width: 20px;
                    height: 20px;
                    border: 2px solid #ddd;
                    border-top: 2px solid #666;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    display: inline-block;
                }}
                </style>
                <div style='
                    background-color: {bg_color};
                    color: {text_color};
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    padding: 20px 24px;
                    height: 250px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 1.2em;
                    font-weight: 500;
                    text-align: center;
                    margin-bottom: 1rem;
                '>
                    <div class="thinking-spinner"></div>
                    {message_text}
                </div>
                """, unsafe_allow_html=True)
        with chat_col2:
            # Show stop button when LLM is busy, but disable if already cancelled
            is_cancelled = st.session_state.get("llm_cancelled", False)
            stop_clicked = st.button(
                "⏹ Stop" if not is_cancelled else "⏹ Stopping...",
                key="stop_chat_btn",
                help="Stop assistant" if not is_cancelled else "Cancellation in progress",
                use_container_width=True,
                disabled=is_cancelled  # Disable button once clicked
            )
            # Show accessibility information for the stop button
            st.markdown(f'<div class="sr-only">💡 {get_component_focus_text("stop_chat_btn")}</div>', unsafe_allow_html=True)
            if stop_clicked and not is_cancelled:
                # Cancel the LLM request - but keep llm_busy=True until the call actually completes
                st.session_state.llm_cancelled = True  # Flag to ignore in-flight responses
                
                # Add placeholder assistant message to maintain conversation flow
                placeholder_message = {"role": "assistant", "content": "*[Response stopped by user]*"}
                st.session_state["chat_messages"].append(placeholder_message)
                
                # Log placeholder message to database if session exists
                session_db_id = st.session_state.get("session_db_id")
                if session_db_id:
                    session_db.log_message(session_db_id, "assistant", "*[Response stopped by user]*", skip_db=SKIP_DB)
                
                st.rerun()
    else:
        # Normal input mode - show text area and send button
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
            # Show accessibility information for the text area
            st.markdown(f'<div class="sr-only">💡 {get_component_focus_text("chat_input_text")}</div>', unsafe_allow_html=True)
        with chat_col2:
            send_clicked = st.button(
                "➤",
                key="send_chat_btn",
                help="Send message button",
                use_container_width=True,
                disabled=st.session_state.get("llm_busy", False) # Disable while LLM is busy
            )
            # Show accessibility information for the send button
            st.markdown(f'<div class="sr-only">💡 {get_component_focus_text("send_chat_btn")}</div>', unsafe_allow_html=True)

        # Sends to LLM on ➤ button click or if Enter is pressed and only one line (simulate send on enter)
        if send_clicked and user_text.strip():
            logger.debug("if send_clicked and user_text.strip()")
            st.session_state["chat_messages"].append({"role": "user", "content": user_text})
            session_db_id = st.session_state.get("session_db_id")
            if session_db_id:
                session_db.log_message(session_db_id, "user", user_text, skip_db=SKIP_DB)
            st.session_state["clear_chat_input"] = True
            # Set both flags immediately for instant UI response
            st.session_state["llm_busy"] = True
            st.session_state["should_call_llm"] = True
            st.session_state["pending_llm"] = False  # Clear pending since we're starting immediately
            st.rerun()
        
        # Show help caption only when not busy
        st.caption("Press the ➤ button to send your message.")
        # Increase the text size of that caption and make it black
        st.markdown("""
        <style>
        /* Style the help caption to be larger and black */
        div[data-testid="stCaptionContainer"]:last-of-type p {
            font-size: 1rem !important;
            color: black !important;
            font-weight: 500 !important;
        }
        </style>
        """, unsafe_allow_html=True)

    
# --- Final Rerun Handling for Session Loading (after all other logic) ---
# After loading a session, clear the rerun flag so the UI is stable and ready for user input.
# This ensures a final clean rerun after _pending_session_load_data has been processed
# This flag is set by the initial "_pending_session_load_data" block now.
if st.session_state.get("_rerun_from_load", False):
    logger.debug("if _rerun_from_load")
    del st.session_state["_rerun_from_load"]
    # No st.rerun() here, as this means we're done with the load sequence.
    # The next action will be user input or Streamlit's idle rerun.

# --- LLM CALL TRIGGER BLOCK: MUST BE AFTER ALL UI RENDERING ---
# This is placed at the end so that all UI (chat history, thinking state) renders first,
# then the synchronous LLM call executes without blocking the UI display
if st.session_state.get("should_call_llm", False) or (st.session_state.get("llm_cancelled", False) and st.session_state.get("llm_busy", False)):
    # Clear the trigger flag to prevent duplicate calls
    if st.session_state.get("should_call_llm", False):
        st.session_state.should_call_llm = False
    
    try:
        # Check if request was cancelled before we even start
        if st.session_state.get("llm_cancelled", False):
            logger.debug("LLM request was cancelled, maintaining stopping state until cleanup")
            # Keep the stopping state active - don't make a new HTTP call
            # The UI will show "Stopping..." until the finally block runs
            pass  # Continue to finally block for cleanup
        else:
            # Make the LLM call
            selected_model = st.session_state.get("selected_model_chatapi", "gemini-2.5-pro")
            current_level = st.session_state.get("level_chatapi", "Select a level")
            messages = [m for m in st.session_state["chat_messages"]]

            logger.debug(f"Attempt to call /score endpoint with model: {selected_model}, level: {current_level}")
            
            # Mark that an HTTP call is in progress
            st.session_state.http_call_in_progress = True
            
            response_content = call_flow_score_endpoint(
                chat_history=convert_chat_messages_to_chat_history(messages),
                level=current_level,
                llm_model_id=selected_model,
            )
            logger.debug(f"Response from /score endpoint: {response_content}")

            # Mark that HTTP call is complete
            st.session_state.http_call_in_progress = False

            # Check if the request was cancelled while we were waiting for the response
            if st.session_state.get("llm_cancelled", False):
                logger.debug("LLM request was cancelled, ignoring response")
            else:
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
        # Mark that HTTP call is complete even on error
        st.session_state.http_call_in_progress = False
    finally:
        # Always clean up state, regardless of whether call was made or cancelled
        logger.debug("LLM block completed - cleaning up state flags")
        st.session_state.llm_busy = False  # Not busy after response
        st.session_state.llm_cancelled = False  # Clear cancellation flag
        st.session_state.http_call_in_progress = False  # Ensure HTTP flag is cleared
        st.rerun()  # Rerun to display the new assistant message and re-enable the button