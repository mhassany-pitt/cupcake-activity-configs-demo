from typing import Dict, Any, Tuple

ACTIVITY_SYSTEM_CONTEXT = {
    "code-completion": (
        "This is a Code Completion (fill-in-the-blank) activity. "
        "Focus on how the missing blank interacts with surrounding syntax, variable types, and control flow."
    ),
    "free-coding": (
        "This is a Free Coding problem. "
        "Focus on algorithmic logic, syntax, edge cases, and problem requirements."
    ),
    "parsons-puzzle": (
        "This is a Parsons Puzzle (drag-and-drop code reordering) activity. "
        "Focus on block selection, logical sequencing, indentation levels, and spotting distractor blocks."
    ),
    "multiple-choice-question": (
        "This is a Multiple Choice conceptual question. "
        "Focus on the underlying programming concept and why specific choices succeed or fail, without naming the correct option letter directly."
    ),
    "parameterized-code-tracing": (
        "This is a Parameterized Code Tracing activity. "
        "Focus on step-by-step mental execution, tracking variable values across iterations/branches, and pinpointing where predicted output diverges."
    ),
    "worked-example": (
        "This is a Worked Example study activity. "
        "Focus on explaining why the highlighted line or code segment works, its role in the program, and the underlying concept."
    ),
    "macro-visualization": (
        "This is a Macro Visualization (program execution trace) activity. "
        "Focus on explaining the current execution step, variable/memory state transitions, and control-flow progression."
    ),
    "markdown": (
        "This is an interactive reading/tutorial activity. "
        "Focus on clarifying the concept, summarizing key ideas, and explaining any embedded code snippet clearly."
    ),
}


class PromptBuilder:
    """Builds activity-aware system and user prompts for hints, feedback, and explanations."""

    @staticmethod
    def detect_activity_type(payload: Dict[str, Any]) -> str:
        """Infers the Cupcake activity type from explicit activityType or payload structure."""
        explicit = (payload.get("activityType") or "").strip().lower()
        if explicit in ACTIVITY_SYSTEM_CONTEXT:
            return explicit
        if "choiceIndex" in payload or "choices" in payload or "question" in payload:
            return "multiple-choice-question"
        if "blocks" in payload or "blockId" in payload:
            return "parsons-puzzle"
        if "userOutput" in payload:
            return "parameterized-code-tracing"
        if "blanks" in payload or "userSelections" in payload or "blankId" in payload:
            return "code-completion"
        if "stepIndex" in payload or "visualizationState" in payload or "frames" in payload:
            return "macro-visualization"
        if "markdownContent" in payload or "sectionTitle" in payload:
            return "markdown"
        if "highlightedCode" in payload or "lineNumber" in payload or "explanationTarget" in payload:
            return "worked-example"
        return "free-coding"

    @classmethod
    def _build_common_context(cls, payload: Dict[str, Any], act_type: str) -> list:
        task = payload.get("task", {}) or {}
        title = task.get("title", payload.get("activityId", "Activity"))
        statement = task.get("statement", "")
        language = payload.get("language", "python")

        parts = [
            f"**Activity Type**: `{act_type}` (Language: `{language}`)",
            f"**Activity Title**: {title}",
        ]
        if statement:
            parts.append(f"\n**Task Statement**:\n{statement}")
        return parts

    @classmethod
    def build_hint_prompt(cls, payload: Dict[str, Any]) -> Tuple[str, str]:
        """Constructs activity-specific system and user prompts for progressive hint generation."""
        act_type = cls.detect_activity_type(payload)
        hint_index = payload.get("hintIndex", 0) + 1
        attempt_count = payload.get("attemptCount", 1)
        code = payload.get("code", "")
        act_context = ACTIVITY_SYSTEM_CONTEXT.get(act_type, ACTIVITY_SYSTEM_CONTEXT["free-coding"])

        system_prompt = (
            "You are an encouraging, expert programming instructor in an interactive learning platform. "
            f"{act_context}\n"
            "Your goal is to guide students using Socratic pedagogy without giving away the full answer. "
            "Tailor your response based on the hint progression:\n"
            "- Hint 1: Point out relevant concepts, keywords, or where to look.\n"
            "- Hint 2: Clarify logic, syntax rules, or specific edge cases.\n"
            "- Hint 3: Provide a concrete pattern or minimal partial example illustrating the solution.\n\n"
            "Formatting guidelines:\n"
            "- Keep your response concise (2-4 sentences or bullet points).\n"
            "- Use clean Markdown with inline code formatting (`like_this`).\n"
            "- Never provide the full completed solution."
        )

        parts = cls._build_common_context(payload, act_type)
        parts.append(f"**Hint Progression Level**: Hint {hint_index} (Student attempt #{attempt_count})")

        if act_type == "multiple-choice-question":
            question = payload.get("question", "")
            choice = payload.get("choice", "")
            if question:
                parts.append(f"\n**Question**: {question}")
            if choice:
                parts.append(f"**Student Selected Choice**: {choice}")
            parts.append("\nGuide the student towards the right concept without naming the correct letter.")
        elif act_type == "parsons-puzzle":
            blocks = payload.get("blocks", [])
            block_snippets = "\n".join(f"- {b.get('snippet', b) if isinstance(b, dict) else b}" for b in blocks)
            parts.append(f"\n**Current Student Blocks Arrangement**:\n{block_snippets}")
            parts.append("\nGuide the student on sequencing, indentation, or block selection.")
        elif act_type == "parameterized-code-tracing":
            user_output = payload.get("userOutput", "")
            parts.append(f"\n**Code**:\n```\n{code}\n```")
            parts.append(f"**Student Predicted Output**:\n```\n{user_output}\n```")
            parts.append("\nHelp the student trace step-by-step where their mental simulation diverged.")
        elif act_type == "code-completion":
            blank_id = payload.get("blankId", "")
            parts.append(f"\n**Code with Completed Blanks**:\n```\n{code}\n```")
            if blank_id:
                parts.append(f"**Target Blank**: `{blank_id}`")
            parts.append("\nGuide the student on what expression or operator belongs in the blank without giving the exact answer.")
        elif act_type == "macro-visualization":
            step_index = payload.get("stepIndex", 0)
            viz_state = payload.get("visualizationState", "")
            parts.append(f"\n**Current Execution Step**: {step_index}")
            if code:
                parts.append(f"**Program Code**:\n```\n{code}\n```")
            if viz_state:
                parts.append(f"**Execution State**: {viz_state}")
            parts.append("\nGive a concise hint about what happens next in the execution trace.")
        elif act_type == "worked-example":
            highlighted = payload.get("highlightedCode", "")
            if code:
                parts.append(f"\n**Example Code**:\n```\n{code}\n```")
            if highlighted:
                parts.append(f"**Focused Segment**: `{highlighted}`")
            parts.append("\nGive a study hint highlighting what to pay attention to in this example.")
        elif act_type == "markdown":
            section = payload.get("sectionTitle", "")
            excerpt = payload.get("markdownContent", "")
            if section:
                parts.append(f"\n**Section**: {section}")
            if excerpt:
                parts.append(f"**Content Excerpt**:\n{excerpt[:800]}")
            parts.append("\nProvide a concise learning tip on the key takeaway from this section.")
        else:
            parts.append(f"\n**Student Code**:\n```\n{code}\n```")
            parts.append("\nProvide a focused hint pointing toward resolving syntax, logic, or missing requirements.")

        return system_prompt, "\n".join(parts)

    @classmethod
    def build_feedback_prompt(cls, payload: Dict[str, Any]) -> Tuple[str, str]:
        """Constructs activity-specific system and user prompts for error and test failure feedback."""
        act_type = cls.detect_activity_type(payload)
        code = payload.get("code", "")
        stderr = payload.get("stderr", "")
        tests = payload.get("tests", [])
        failed_count = payload.get("failedTests", 0)
        tc_title = payload.get("testcaseTitle", "")
        act_context = ACTIVITY_SYSTEM_CONTEXT.get(act_type, ACTIVITY_SYSTEM_CONTEXT["free-coding"])

        system_prompt = (
            "You are a friendly, precise programming debugging tutor. "
            f"{act_context}\n"
            "Analyze the student's attempt or failure and explain:\n"
            "1. Exactly what went wrong (in clear, beginner-friendly terms).\n"
            "2. The root cause (e.g. off-by-one, wrong operator, ordering, syntax error, or misconception).\n"
            "3. The next actionable step to fix it.\n\n"
            "Guidelines:\n"
            "- Keep explanation between 2 to 4 sentences.\n"
            "- Use clean Markdown and inline code tags.\n"
            "- Be constructive and encouraging."
        )

        parts = cls._build_common_context(payload, act_type)
        if tc_title:
            parts.append(f"**Failing Testcase**: {tc_title}")
        if failed_count:
            parts.append(f"**Failed Tests Count**: {failed_count} of {len(tests)}")
        if stderr:
            parts.append(f"\n**Execution Error / Traceback**:\n```\n{stderr}\n```")
        if code:
            parts.append(f"\n**Student Code**:\n```\n{code}\n```")
        if act_type == "multiple-choice-question":
            choice = payload.get("choice", "")
            if choice:
                parts.append(f"**Selected Choice**: {choice}")
        if act_type == "parameterized-code-tracing":
            user_output = payload.get("userOutput", "")
            if user_output:
                parts.append(f"**Predicted Output**: `{user_output}`")
        if tests:
            test_summary = "\n".join(
                f"- Test '{t.get('title', t.get('name', 'Case'))}': passed={t.get('passed', False)}"
                for t in tests[:5]
            )
            parts.append(f"\n**Testcases Summary**:\n{test_summary}")

        parts.append("\nProvide helpful, formative feedback diagnosing the failure and advising how to correct it.")
        return system_prompt, "\n".join(parts)

    @classmethod
    def build_explanation_prompt(cls, payload: Dict[str, Any]) -> Tuple[str, str]:
        """Constructs activity-specific system and user prompts for detailed explanations."""
        act_type = cls.detect_activity_type(payload)
        code = payload.get("code", "")
        highlighted = payload.get("highlightedCode", "") or payload.get("snippet", "")
        blank_id = payload.get("blankId", "")
        block_id = payload.get("blockId", "")
        user_selection = payload.get("userSelection", "")
        existing_explanation = payload.get("existingExplanation", "")
        act_context = ACTIVITY_SYSTEM_CONTEXT.get(act_type, ACTIVITY_SYSTEM_CONTEXT["free-coding"])

        system_prompt = (
            "You are a clear, insightful programming instructor explaining a specific part of an activity. "
            f"{act_context}\n"
            "Explain *why* this code/element works (or why the student's choice behaves as it does) and how it connects to the rest of the problem.\n\n"
            "Guidelines:\n"
            "- Keep the explanation concise (2-4 sentences).\n"
            "- Use clean Markdown with inline code formatting (`like_this`).\n"
            "- Tailor your explanation directly to the specific blank, block, line, or visualization step."
        )

        parts = cls._build_common_context(payload, act_type)
        if code:
            parts.append(f"\n**Full Code Context**:\n```\n{code}\n```")
        if highlighted:
            parts.append(f"**Focused Code / Segment**:\n```\n{highlighted}\n```")
        if blank_id:
            parts.append(f"**Blank ID**: `{blank_id}`")
        if block_id:
            parts.append(f"**Block ID**: `{block_id}`")
        if user_selection:
            parts.append(f"**Student Input / Selection**: `{user_selection}`")
        if act_type == "macro-visualization":
            step_index = payload.get("stepIndex", 0)
            viz_state = payload.get("visualizationState", "")
            parts.append(f"**Step Index**: {step_index}")
            if viz_state:
                parts.append(f"**State Snapshot**: {viz_state}")
        if act_type == "markdown":
            section = payload.get("sectionTitle", "")
            excerpt = payload.get("markdownContent", "")
            if section:
                parts.append(f"**Section**: {section}")
            if excerpt:
                parts.append(f"**Content**:\n{excerpt[:1200]}")
        if existing_explanation:
            parts.append(f"\n**Existing Static Explanation (expand or personalize without repeating verbatim)**:\n{existing_explanation}")

        parts.append("\nProvide a clear, focused explanation tailored to this activity.")
        return system_prompt, "\n".join(parts)
