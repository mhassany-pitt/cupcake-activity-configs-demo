# Cupcake Activity Configs Demo (Flask + Ollama Cloud)

A minimal, extensible remote Python application built with **Flask** that serves as an external backend for **Cupcake Activity Configs** (`/api/v1/activity-services/*`).

This demo connects to **Ollama Cloud** (or any remote Ollama instance) to deliver:
- **Progressive AI Hints** (`/hints` with SSE streaming)
- **Formative Feedback on Errors** (`/feedback` with SSE streaming)
- **Submission Evaluation** (`/evaluate` JSON endpoint)
- **Problem Reporting** (`/report` JSON endpoint)
- **Service Health Check** (`/health` JSON endpoint)

It is designed to target **Python** while dynamically supporting **all Cupcake activity types**:
1. `free-coding` (Writing complete solutions)
2. `code-completion` (Filling in syntax blanks)
3. `parsons-puzzle` (Reordering and indenting code blocks)
4. `parameterized-code-tracing` (Predicting output and variable state)
5. `multiple-choice-question` (Conceptual choices and reasoning)

---

## 1. Quickstart

### Prerequisites
- Python 3.9+ installed
- Active Ollama Cloud account or running Ollama server

### Setup Virtual Environment & Install Dependencies
```bash
cd cupcake-activity-configs-demo

# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install requirements
pip install -r requirements.txt
```

### Configure Environment Variables
Copy `.env.example` to `.env` and fill in your Ollama credentials:
```bash
cp .env.example .env
```

Edit `.env`:
```env
PORT=8098
HOST=0.0.0.0
DEBUG=True

# Ollama Cloud credentials
OLLAMA_HOST=https://api.ollama.ai
OLLAMA_API_KEY=your_ollama_cloud_api_key_here
OLLAMA_MODEL=qwen2.5:latest
```

### Run the Flask Application
```bash
python app.py
```
The server will start at: `http://localhost:8098`

Verify connectivity:
```bash
curl http://localhost:8098/health
```

---

## 2. Connecting with Cupcake Activity Configs

To route activity requests through this service:

1. In Cupcake, create a new Activity Config (or use the API endpoint `POST /api/v1/activity-configs`).
2. Use the contents of [`sample-config.json`](./sample-config.json) as the configuration payload.
3. Cupcake will assign a 6-character Configuration ID (e.g., `cfg-demo1`).
4. In your activity viewer URL, append `?config=cfg-demo1` (e.g., `http://localhost:4200/#/activities/python-sample/code-completion.yaml?config=cfg-demo1`).

### How Cupcake Dispatches Requests
```
[Cupcake Frontend Viewer]
        │
        ▼ (POST /api/v1/activity-services/hints?config=cfg-demo1)
[Cupcake API Gateway (SSRF Guard & Auth)]
        │
        ▼ (POST http://localhost:8098/hints)
[Flask App (PromptBuilder + OllamaClient)]
        │
        ▼ (SSE Stream: data: {"text": "..."})
[Cupcake Markdown Viewer (Live streaming tab flap)]
```

---

## 3. Endpoints & Protocol

### `POST /hints`
- **Wire Protocol**: Server-Sent Events (`Content-Type: text/event-stream`).
- **Response Headers**:
  - `x-has-next`: `true` or `false` (indicates whether more progressive hints remain).
  - `x-total-hints`: Total progressive hint count (default: 3).
- **Chunk Format**:
  ```text
  data: {"text": "Consider using"}

  data: {"text": " the `len()` function..."}

  data: [DONE]
  ```

### `POST /feedback`
- **Wire Protocol**: Server-Sent Events (`Content-Type: text/event-stream`).
- Explains runtime exceptions, assertion errors, and logic discrepancies concisely.

### `POST /evaluate`
- **Wire Protocol**: Standard JSON (`Content-Type: application/json`).
- **Response**:
  ```json
  {
    "passed": true,
    "tests": [
      {
        "name": "Bob's Account",
        "passed": true,
        "stdout": "Deposited 100\nWithdrew 50\nBalance: 250\n",
        "stderr": "",
        "expected": "Deposited 100\nWithdrew 50\nBalance: 250",
        "actual": "Deposited 100\nWithdrew 50\nBalance: 250"
      }
    ]
  }
  ```

### `POST /report`
- Receives student bug or content flags submitted from the Activity Footer.

### `GET /health`
- Verifies server health and prints connected Ollama model tags.

---

## 4. Extending this Demo

### Adding a New Language
In `services/prompt_builder.py`, modify `build_hint_prompt` to inject idioms and conventions for other languages (e.g., Java, C++, SQL).

### Customizing Prompts & Socratic Style
Edit `services/prompt_builder.py` to change pedagogical tone, strictness, or formatting rules.

### Custom Grading / Sandboxing
In `services/evaluator.py`, replace `subprocess.run` with Docker, Firejail, or an AST-based grader to safely evaluate complex submissions.
