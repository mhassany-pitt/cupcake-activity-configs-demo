import json
import logging
import uuid
from flask import Flask, request, Response, jsonify
from flask_cors import CORS
from config import config
from services.ollama_client import OllamaClient
from services.prompt_builder import PromptBuilder
from services.evaluator import SubmissionEvaluator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cupcake-demo")

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests from Cupcake frontend / API

ollama_client = OllamaClient()


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint reporting server status and Ollama connectivity."""
    ollama_status = ollama_client.check_health()
    return jsonify({
        "status": "healthy",
        "service": "cupcake-activity-configs-demo",
        "port": config.PORT,
        "ollama": ollama_status,
    })


@app.route("/hints", methods=["POST"])
def get_hints():
    """
    Progressive hint endpoint streaming SSE tokens for all Cupcake activity types.
    Matches the ActivityServices dispatch protocol.
    """
    payload = request.get_json(silent=True) or {}
    logger.info(f"[/hints] Received hint request: activityId={payload.get('activityId')}, hintIndex={payload.get('hintIndex')}")

    system_prompt, user_prompt = PromptBuilder.build_hint_prompt(payload)

    hint_index = int(payload.get("currentHintIndex") if payload.get("currentHintIndex") is not None else payload.get("hintIndex", 0))
    total_hints = payload.get("totalHints", 3)
    has_next = (hint_index + 1) < total_hints

    def stream_generator():
        for chunk in ollama_client.stream_chat(system_prompt, user_prompt):
            data = json.dumps({"text": chunk})
            yield f"data: {data}\n\n"
        yield "data: [DONE]\n\n"

    response = Response(stream_generator(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    response.headers["x-has-next"] = "true" if has_next else "false"
    response.headers["x-total-hints"] = str(total_hints)
    return response


@app.route("/feedback", methods=["POST"])
def get_feedback():
    """
    On-demand formative feedback endpoint streaming SSE tokens for failed attempts.
    """
    payload = request.get_json(silent=True) or {}
    logger.info(f"[/feedback] Received feedback request: activityId={payload.get('activityId')}, passed={payload.get('passed')}")

    feedback_index = int(payload.get("feedbackIndex") or 0)
    total_feedback = int(payload.get("totalFeedback") or 2)
    has_next = (feedback_index + 1) < total_feedback

    system_prompt, user_prompt = PromptBuilder.build_feedback_prompt(payload)

    def stream_generator():
        for chunk in ollama_client.stream_chat(system_prompt, user_prompt):
            data = json.dumps({"text": chunk})
            yield f"data: {data}\n\n"
        yield "data: [DONE]\n\n"

    response = Response(stream_generator(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    response.headers["x-has-next"] = "true" if has_next else "false"
    return response


@app.route("/explanation", methods=["POST"])
def get_explanation():
    """
    On-demand explanation endpoint streaming SSE tokens for blanks, blocks, lines, or visualization steps.
    """
    payload = request.get_json(silent=True) or {}
    logger.info(f"[/explanation] Received explanation request: activityId={payload.get('activityId')}, activityType={payload.get('activityType')}")

    explanation_index = int(payload.get("explanationIndex") or 0)
    total_explanations = int(payload.get("totalExplanations") or 2)
    has_next = (explanation_index + 1) < total_explanations

    system_prompt, user_prompt = PromptBuilder.build_explanation_prompt(payload)

    def stream_generator():
        for chunk in ollama_client.stream_chat(system_prompt, user_prompt):
            data = json.dumps({"text": chunk})
            yield f"data: {data}\n\n"
        yield "data: [DONE]\n\n"

    response = Response(stream_generator(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    response.headers["x-has-next"] = "true" if has_next else "false"
    return response


@app.route("/evaluate", methods=["POST"])
def evaluate():
    """
    Code evaluation endpoint running Python submissions against testcases.
    Returns: { "passed": bool, "tests": [...] }
    """
    payload = request.get_json(silent=True) or {}
    logger.info(f"[/evaluate] Evaluating submission: path={payload.get('path')}")

    result = SubmissionEvaluator.evaluate(payload)
    return jsonify(result)


@app.route("/report", methods=["POST"])
def report():
    """
    Problem reporting endpoint called when a learner flags an issue via the Activity Footer.
    """
    payload = request.get_json(silent=True) or {}
    report_id = f"rep_{uuid.uuid4().hex[:8]}"
    logger.info(f"[/report] Student issue report received [{report_id}]: {payload}")

    return jsonify({
        "status": "received",
        "reportId": report_id,
        "message": "Thank you for your report. The instructor team has been notified.",
    })


if __name__ == "__main__":
    logger.info(f"Starting Cupcake Activity Configs Demo on {config.HOST}:{config.PORT} (model: {config.OLLAMA_MODEL})")
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
    )
