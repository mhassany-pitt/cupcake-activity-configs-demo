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
        "This is a Multiple Choice conceptual question (not a free-coding task). "
        "Focus on the underlying programming concept and why specific choices succeed or fail, without naming the correct option letter directly."
    ),
    "parameterized-code-tracing": (
        "This is a Parameterized Code Tracing activity. "
        "Focus on step-by-step mental execution, tracking variable values across iterations/branches, and pinpointing where predicted output diverges."
    ),
    "worked-example": (
        "This is a Worked Example study activity. "
        "Focus on explaining how the example works, what its execution output demonstrates, and the underlying programming concept."
    ),
}


def _format_history(history: Any, label: str) -> str:
    if not isinstance(history, list) or not history:
        return ""
    items = [
        f"{idx + 1}. {str(entry or '').strip()}"
        for idx, entry in enumerate(history)
        if str(entry or "").strip()
    ]
    if not items:
        return ""
    return f"\n**Previous {label} Already Shown (do not repeat verbatim; build on them)**:\n" + "\n".join(items)


class PromptBuilder:
    """Builds activity-aware system and user prompts for hints, feedback, and explanations."""

    @staticmethod
    def detect_activity_type(payload: Dict[str, Any]) -> str:
        """Infers the Cupcake activity type from explicit activityType or payload structure."""
        explicit = (payload.get("activityType") or "").strip().lower()
        if explicit in ACTIVITY_SYSTEM_CONTEXT:
            return explicit
        if any(k in payload for k in ("selectedChoice", "selectedChoiceIndex", "choiceIndex", "choices", "question")):
            return "multiple-choice-question"
        if any(k in payload for k in ("blocks", "blockId", "solvedBlocks")):
            return "parsons-puzzle"
        if "userOutput" in payload or "actual" in payload:
            return "parameterized-code-tracing"
        if any(k in payload for k in ("blanks", "userSelections", "blankId")):
            return "code-completion"
        if any(k in payload for k in ("highlightedCode", "lineNumber", "explanationTarget")):
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

    @staticmethod
    def _format_mcq_choices(payload: Dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        selected_idx = payload.get("selectedChoiceIndex")
        if selected_idx is None and isinstance(payload.get("selectedChoice"), dict):
            selected_idx = payload["selectedChoice"].get("index")
        lines = []
        for idx, c in enumerate(choices):
            letter = chr(65 + idx)
            body = c.get("body", "") if isinstance(c, dict) else str(c)
            is_sel = (isinstance(c, dict) and c.get("selected")) or selected_idx == idx
            sel_tag = " [SELECTED BY STUDENT]" if is_sel else ""
            lines.append(f"- **{letter}**{sel_tag}: {body}")
        return "\n".join(lines)

    @classmethod
    def build_hint_prompt(cls, payload: Dict[str, Any]) -> Tuple[str, str]:
        """Constructs activity-specific system and user prompts for progressive hint generation."""
        act_type = cls.detect_activity_type(payload)
        raw_idx = payload.get("currentHintIndex")
        if raw_idx is None:
            raw_idx = payload.get("hintIndex", 0)
        hint_index = int(raw_idx or 0) + 1
        attempt_count = int(payload.get("attemptCount") or 1)
        code = payload.get("code", "")
        act_context = ACTIVITY_SYSTEM_CONTEXT.get(act_type, ACTIVITY_SYSTEM_CONTEXT["free-coding"])

        system_prompt = (
            "You are an encouraging, expert programming instructor in an interactive learning platform. "
            f"{act_context}\n"
            "Your goal is to guide students using Socratic pedagogy without giving away the full answer. "
            "Tailor your response based on the hint progression:\n"
            "- Hint 1: Point out relevant concepts, keywords, or where to look.\n"
            "- Hint 2: Clarify logic, syntax rules, or specific edge cases.\n"
            "- Hint 3: Provide a concrete pattern or minimal partial focus without giving away the answer.\n\n"
            "Formatting guidelines:\n"
            "- Keep your response concise (2-4 sentences or bullet points).\n"
            "- Use clean Markdown with inline code formatting (`like_this`).\n"
            "- Never provide the full completed solution."
        )

        parts = cls._build_common_context(payload, act_type)
        parts.append(f"**Hint Progression Level**: Hint {hint_index} (Student attempt #{attempt_count})")

        if act_type == "multiple-choice-question":
            question = payload.get("question", "")
            formatted_choices = cls._format_mcq_choices(payload)
            if question:
                parts.append(f"\n**Question**: {question}")
            if code:
                parts.append(f"\n**Reference Code**:\n```\n{code}\n```")
            if formatted_choices:
                parts.append(f"\n**Choices**:\n{formatted_choices}")
            parts.append(
                "\nGuide the student toward the underlying concept so they can evaluate the choices themselves. "
                "Do NOT ask them to write code and do NOT reveal the correct option letter."
            )
        elif act_type == "parsons-puzzle":
            blocks = payload.get("blocks", [])
            selections = payload.get("userSelections", [])
            indents = payload.get("userIndents", [])
            if code:
                parts.append(f"\n**Current Assembled Code**:\n```\n{code}\n```")
            if isinstance(selections, list) and selections:
                arranged = "\n".join(
                    f"{i + 1}. (indent={indents[i] if isinstance(indents, list) and i < len(indents) else 0}) {s or '<empty>'}"
                    for i, s in enumerate(selections)
                )
                parts.append(f"\n**Current Slot Arrangement**:\n{arranged}")
            elif isinstance(blocks, list) and blocks:
                block_snippets = "\n".join(
                    f"- {b.get('snippet', b) if isinstance(b, dict) else b}" for b in blocks
                )
                parts.append(f"\n**Current Student Blocks Arrangement**:\n{block_snippets}")
            parts.append("\nGuide the student on block selection, sequencing, or indentation.")
        elif act_type == "parameterized-code-tracing":
            user_output = payload.get("userOutput", "")
            parts.append(f"\n**Code to Trace**:\n```\n{code}\n```")
            parts.append(f"**Student Predicted Output**:\n```\n{user_output}\n```")
            parts.append("\nHelp the student trace step-by-step where their mental simulation diverged.")
        elif act_type == "code-completion":
            blank_id = payload.get("blankId", "")
            parts.append(f"\n**Code with Current Blanks**:\n```\n{code}\n```")
            if blank_id:
                parts.append(f"**Target Blank**: `{blank_id}`")
            parts.append("\nGuide the student on what expression or operator belongs in the blank without giving the exact answer.")
        else:
            parts.append(f"\n**Student Code**:\n```\n{code}\n```")
            parts.append("\nProvide a focused hint pointing toward resolving syntax, logic, or missing requirements.")

        history_text = _format_history(payload.get("hintsHistory"), "Hints")
        if history_text:
            parts.append(history_text)

        return system_prompt, "\n".join(parts)

    @classmethod
    def build_feedback_prompt(cls, payload: Dict[str, Any]) -> Tuple[str, str]:
        """Constructs activity-specific system and user prompts for formative feedback."""
        act_type = cls.detect_activity_type(payload)
        feedback_index = int(payload.get("feedbackIndex") or 0) + 1
        act_context = ACTIVITY_SYSTEM_CONTEXT.get(act_type, ACTIVITY_SYSTEM_CONTEXT["free-coding"])

        if act_type == "worked-example":
            system_prompt = (
                "You are a clear, supportive programming instructor helping a student study a Worked Example. "
                f"{act_context}\n"
                "Explain what the shown program execution output demonstrates, how the example code produces it, and the key takeaway.\n"
                "Guidelines:\n"
                "- Keep the feedback concise (2-4 sentences) and use clean Markdown.\n"
                "- Do NOT tell the student to fix their code—this is a study example."
            )
            parts = cls._build_common_context(payload, act_type)
            if payload.get("testcaseTitle"):
                parts.append(f"**Execution Case**: {payload['testcaseTitle']}")
            if payload.get("code"):
                parts.append(f"\n**Example Code**:\n```\n{payload['code']}\n```")
            if payload.get("stderr"):
                parts.append(f"\n**Execution Error / Output Note**:\n```\n{payload['stderr']}\n```")
            history_text = _format_history(payload.get("feedbackHistory"), "Feedback")
            if history_text:
                parts.append(history_text)
            parts.append(f"\n**Feedback Step**: #{feedback_index}")
            return system_prompt, "\n".join(parts)

        if act_type == "multiple-choice-question":
            selected = payload.get("selectedChoice") or {}
            is_correct = bool(payload.get("isCorrect") is True or (isinstance(selected, dict) and selected.get("isCorrect") is True))
            system_prompt = (
                "You are a friendly, precise programming instructor giving conceptual feedback on a Multiple Choice Question. "
                f"{act_context}\n"
                + (
                    "The student selected the CORRECT option. Confirm why their reasoning/choice is right and reinforce the key concept."
                    if is_correct
                    else "The student selected an INCORRECT option. Explain the misconception behind their selected choice and guide them toward the right concept without assuming they are writing or compiling code."
                )
                + "\n\nGuidelines:\n- Keep feedback between 2 to 4 sentences.\n- Use clean Markdown with inline code formatting."
            )
            parts = cls._build_common_context(payload, act_type)
            if payload.get("question"):
                parts.append(f"\n**Question**: {payload['question']}")
            if payload.get("code"):
                parts.append(f"\n**Reference Code**:\n```\n{payload['code']}\n```")
            formatted_choices = cls._format_mcq_choices(payload)
            if formatted_choices:
                parts.append(f"\n**Choices**:\n{formatted_choices}")
            if isinstance(selected, dict) and selected.get("body"):
                parts.append(f"\n**Selected Choice**: {selected['body']} (Correct: {is_correct})")
            history_text = _format_history(payload.get("feedbackHistory"), "Feedback")
            if history_text:
                parts.append(history_text)
            parts.append(f"\n**Feedback Step**: #{feedback_index}")
            return system_prompt, "\n".join(parts)

        is_passed = payload.get("passed") is True
        code = payload.get("code", "")
        stderr = payload.get("stderr", "")
        tests = payload.get("tests", [])
        failed_count = int(payload.get("failedTests") or 0)
        tc_title = payload.get("testcaseTitle", "")

        system_prompt = (
            "You are a friendly, precise programming tutor. "
            f"{act_context}\n"
            "The student PASSED this testcase/check! Briefly affirm why their solution works well and highlight one clean concept or edge case they handled.\n"
            "Guidelines:\n- Keep feedback between 2 to 4 sentences.\n- Use clean Markdown and inline code tags."
            if is_passed
            else "You are a friendly, precise programming debugging tutor. "
            f"{act_context}\n"
            "Analyze the student's attempt or failure and explain:\n"
            "1. Exactly what went wrong (in clear, beginner-friendly terms).\n"
            "2. The root cause (e.g. off-by-one, wrong operator, ordering, indentation, syntax error, or misconception).\n"
            "3. The next actionable step to fix it.\n\n"
            "Guidelines:\n- Keep explanation between 2 to 4 sentences.\n- Use clean Markdown and inline code tags.\n- Be constructive and encouraging."
        )

        parts = cls._build_common_context(payload, act_type)
        parts.append(f"**Feedback Step**: #{feedback_index} (Passed: {is_passed})")
        if tc_title:
            parts.append(f"**Testcase**: {tc_title}")
        if failed_count:
            parts.append(f"**Failed Tests Count**: {failed_count} of {len(tests)}")
        if stderr:
            parts.append(f"\n**Execution Error / Traceback**:\n```\n{stderr}\n```")
        if code:
            parts.append(f"\n**Student Code**:\n```\n{code}\n```")

        if act_type == "parsons-puzzle":
            selections = payload.get("userSelections", [])
            indents = payload.get("userIndents", [])
            if isinstance(selections, list) and selections:
                arranged = "\n".join(
                    f"{i + 1}. (indent={indents[i] if isinstance(indents, list) and i < len(indents) else 0}) {s or '<empty>'}"
                    for i, s in enumerate(selections)
                )
                parts.append(f"\n**Placed Blocks & Indentation**:\n{arranged}")

        if act_type == "parameterized-code-tracing":
            if payload.get("userOutput") is not None:
                parts.append(f"**Student Predicted Output**: `{payload['userOutput']}`")
            if payload.get("actual") is not None:
                parts.append(f"**Actual Program Output**: `{payload['actual']}`")
            if payload.get("expected") is not None:
                parts.append(f"**Expected Output**: `{payload['expected']}`")

        if isinstance(tests, list) and tests:
            test_summary = "\n".join(
                f"- Test '{t.get('title') or t.get('name') or 'Case'}': passed={bool(t.get('passed'))}"
                for t in tests[:5]
                if isinstance(t, dict)
            )
            if test_summary:
                parts.append(f"\n**Testcases Summary**:\n{test_summary}")

        history_text = _format_history(payload.get("feedbackHistory"), "Feedback")
        if history_text:
            parts.append(history_text)

        return system_prompt, "\n".join(parts)

    @classmethod
    def build_explanation_prompt(cls, payload: Dict[str, Any]) -> Tuple[str, str]:
        """Constructs activity-specific system and user prompts for detailed explanations."""
        act_type = cls.detect_activity_type(payload)
        explanation_index = int(payload.get("explanationIndex") or 0) + 1
        code = payload.get("code", "")
        highlighted = payload.get("highlightedCode") or payload.get("snippet", "")
        blank_id = payload.get("blankId", "")
        block_id = payload.get("blockId", "")
        user_selection = payload.get("userSelection", "")
        act_context = ACTIVITY_SYSTEM_CONTEXT.get(act_type, ACTIVITY_SYSTEM_CONTEXT["free-coding"])

        system_prompt = (
            "You are a clear, insightful programming instructor explaining a specific part of an activity. "
            f"{act_context}\n"
            "Explain *why* this code/element works (or why the student's choice behaves as it does) and how it connects to the rest of the problem.\n\n"
            "Guidelines:\n"
            "- Keep the explanation concise (2-4 sentences).\n"
            "- Use clean Markdown with inline code formatting (`like_this`).\n"
            "- Tailor your explanation directly to the specific blank, block, or highlighted line."
        )

        parts = cls._build_common_context(payload, act_type)
        parts.append(f"**Explanation Step**: #{explanation_index}")
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

        history_text = _format_history(payload.get("explanationsHistory"), "Explanations")
        if history_text:
            parts.append(history_text)

        parts.append("\nProvide a clear, focused explanation tailored to this activity.")
        return system_prompt, "\n".join(parts)
