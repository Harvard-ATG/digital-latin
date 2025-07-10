# Streamlit UI for Gemini Integration

This project provides a Streamlit-based frontend for interacting with the Gemini pipeline. It allows users to select models, set system prompts, engage in multi-turn interactions, and save sessions.

## Features
- **Model Selection**: Choose from a list of allowed models.
- **System Prompts**: Set predefined prompts for Level I and Level II Latin translations.
- **Multi-Turn Interaction**: Chat with the Gemini pipeline and view the conversation history.
- **Session Management**: Save and load user sessions.

## Prerequisites
- Python 3.12 or later
- `pip` installed

## Setup Instructions

### 1. Clone the Repository
Navigate to the `app` directory:
```bash
cd /Users/kevingray/codebase/harvard-atg/digital-latin/app
```

### 2. Create a Virtual Environment
Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
Install the required Python packages:
```bash
pip install -r requirements.txt
```

### 4. Run the Application
Start the Streamlit application:
```bash
streamlit run streamlit_ui_main.py
# or
streamlit run streamlit_ui_chatapi.py --server.port 8502
```

### 5. Access the UI
Open your browser and navigate to:
```
http://localhost:8501
```

## Docker & Docker Compose

You can run both apps using Docker Compose. This will start both services, each on its own port (8501 and 8502), sharing the same code and database files.

```bash
docker-compose up --build
```

- Main app: http://localhost:8501
- Chat API app: http://localhost:8502

## Exposing Your App with ngrok

To share your local Streamlit app with others, use [ngrok](https://ngrok.com/docs):

1. **Install ngrok**
   - Download from https://ngrok.com/download or use Homebrew:
     ```sh
     brew install ngrok/ngrok/ngrok
     ```
2. **Start your Streamlit app(s)** (see above)
3. **Expose your app**
   - In a new terminal, run:
     ```sh
     ngrok http 8501
     ngrok http 8502
     ```
   - ngrok will display a public forwarding URL (e.g., `https://xxxx.ngrok-free.app`). Share this link to give others access.

For more details, see the [ngrok documentation](https://ngrok.com/docs).

## File Structure
- `streamlit_ui_main.py`: The main Streamlit application.
- `streamlit_ui_chatapi.py`: The Streamlit chat API application.
- `gemini_pipeline.py`: The Gemini pipeline integration.
- `requirements.txt`: List of dependencies.
- `level1_system_prompt.jinja2`, `level2_system_prompt.jinja2`: Prompt templates.
- `sessions.db`: SQLite database for session management.
- `docker-compose.yml`, `Dockerfile`: Containerization setup.

## Troubleshooting
- Ensure all dependencies are installed.
- Verify the `.env` file contains the required environment variables.
- Check the terminal for error messages if the application fails to start.

## License
This project is licensed under the Apache License 2.0.

## Further Reading (Streamlit Official Documentation)

- **Understanding Streamlit's client-server architecture:**
  - Explains how Streamlit apps have a Python backend (server) and a browser frontend (client), and how they communicate. Good for understanding what runs where and how Streamlit handles UI updates.
  - [Understanding Streamlit's client-server architecture](https://docs.streamlit.io/develop/concepts/architecture/architecture)

- **Intro to custom components:**
  - Shows how to extend Streamlit with your own HTML/JS/React widgets, and the basics of using or building custom components.
  - [Intro to custom components](https://docs.streamlit.io/develop/concepts/custom-components/intro)

- **Create a Component:**
  - Step-by-step guide to building your own Streamlit Component, including sending data between Python and JavaScript.
  - [Create a Component](https://docs.streamlit.io/develop/concepts/custom-components/create)

---

## Community-Contributed Resources and Other Perspectives

- **Streamlit Components Gallery:**
  - A collection of community-built Streamlit Components, many of which use JavaScript/React. Browse, discover, and plug in new widgets and add new features to your app using community-built Streamlit Components. Many use JavaScript/React, but you only need Python—Streamlit handles the JavaScript for you.
  - [Streamlit Components Gallery](https://streamlit.io/components)

- **Streamlit in 5 Minutes (YouTube, Data Professor):**
  - Quick, beginner-friendly overview of Streamlit's core ideas and workflow.
  - [Watch here](https://www.youtube.com/watch?v=UI4f4iiVT6c)
  
- **5 Things I Wish I Knew Before Learning Streamlit (YouTube, Data Professor):**
  - Covers key tips and common pitfalls for new Streamlit users, helping you get started faster and avoid mistakes.
  - [Watch here](https://www.youtube.com/watch?v=IOYHVPPbZII)

- **How to Control the Layout in Streamlit in 20 Minutes! (Streamlit Tutorials 02, Chanin Nantasenamat):**
  - A practical walkthrough on customizing and controlling layout in Streamlit apps, including columns, containers, and advanced layout tips.
  - [Watch here](https://www.youtube.com/watch?v=saOv9z6Fk88)

## Docker Entrypoint Script Permissions

The `entrypoint.sh` script is automatically made executable during the Docker build process (see the Dockerfile). You do **not** need to run `chmod +x entrypoint.sh` manually. This ensures the script always runs correctly for all contributors and CI/CD environments.

## Example: Inspecting Your PostgreSQL Database from the Container

To view your tables and data directly from the running PostgreSQL container:

1. **Open a shell in the postgres container:**
   ```sh
   docker-compose exec postgres bash
   ```
2. **Connect to PostgreSQL using psql:**
   ```sh
   psql -U $POSTGRES_USER -d $POSTGRES_DB
   # For your setup, typically:
   psql -U postgres -d sessions
   ```
3. **List tables:**
   ```sql
   \dt
   ```
4. **View all data in the sessions table:**
   ```sql
   SELECT * FROM sessions;
   ```
5. **To exit psql:**
   ```
   \q
   ```

