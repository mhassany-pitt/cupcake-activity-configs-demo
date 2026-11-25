from typing import Dict, Any, Tuple

class PromptBuilder:
    """Builds activity-aware system and user prompts for hints and feedback."""

    @staticmethod
    def detect_activity_type(payload: Dict[str, Any]) -> str:
        """Infers the Cupcake activity type from the request payload structure."""
        if "choiceIndex" in payload or "choices" in payload or "question" in payload:
            return "multiple-choice-question"
        if "blocks" in payload:
            return "parsons-puzzle"
        if "userOutput" in payload:
            return "parameterized-code-tracing"
        if "blanks" in payload or "userSelections" in payload:
            return "code-completion"
        # Default to free-coding
        return "free-coding"

    @classmethod
    def build_hint_prompt(cls, payload: Dict[str, Any]) -> Tuple[str, str]:
        """Constructs system and user prompts for progressive hint generation."""
        act_type = cls.detect_activity_type(payload)
        hint_index = payload.get("hintIndex", 0) + 1  # 1-indexed for prompt
        attempt_count = payload.get("attemptCount", 1)
        task = payload.get("task", {})
        title = task.get("title", payload.get("activityId", "Activity"))
        statement = task.get("statement", "")
        code = payload.get("code", "")
        language = payload.get("language", "python")

        system_prompt = (
            "You are an encouraging, expert Python programming instructor in an interactive learning platform. "
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

        user_content_parts = [
            f"**Activity Type**: `{act_type}` (Language: `{language}`)",
            f"**Activity Title**: {title}",
            f"**Hint Progression Level**: Hint {hint_index} (Student attempt #{attempt_count})",
        ]

        if statement:
            user_content_parts.append(f"\n**Task Statement**:\n{statement}")

        if act_type == "multiple-choice-question":
            question = payload.get("question", statement)
            choice = payload.get("choice", "")
            user_content_parts.append(f"\n**Question**: {question}")
            if choice:
                user_content_parts.append(f"**Student Selected Choice**: {choice}")
            user_content_parts.append(
                "\nPlease guide the student towards understanding the correct concept without explicitly naming the letter or correct choice."
            )

        elif act_type == "parsons-puzzle":
            blocks = payload.get("blocks", [])
            block_snippets = "\n".join(f"- {b.get('snippet', b)}" for b in blocks)
            user_content_parts.append(f"\n**Current Student Blocks Arrangement**:\n{block_snippets}")
            user_content_parts.append(
                "\nPlease guide the student on proper sequencing, indentation, or block selection."
            )

        elif act_type == "parameterized-code-tracing":
            user_output = payload.get("userOutput", "")
            user_content_parts.append(f"\n**Python Code**:\n```python\n{code}\n```")
            user_content_parts.append(f"**Student Predicted Output**:\n```\n{user_output}\n```")
            user_content_parts.append(
                "\nHelp the student trace the program step-by-step to identify where their mental simulation diverged."
            )

        elif act_type == "code-completion":
            user_content_parts.append(f"\n**Code with Completed Blanks**:\n```python\n{code}\n```")
            user_content_parts.append(
                "\nGuide the student on which blank or operator to check without writing the exact code replacement."
            )

        else:  # free-coding
            user_content_parts.append(f"\n**Student Python Code**:\n```python\n{code}\n```")
            user_content_parts.append(
                "\nProvide a focused hint pointing the student towards resolving syntax, logic, or missing requirements."
            )

        user_prompt = "\n".join(user_content_parts)
        return system_prompt, user_prompt

    @classmethod
    def build_feedback_prompt(cls, payload: Dict[str, Any]) -> Tuple[str, str]:
        """Constructs system and user prompts for error and test failure feedback."""
        act_type = cls.detect_activity_type(payload)
        code = payload.get("code", "")
        stderr = payload.get("stderr", "")
        tests = payload.get("tests", [])
        failed_count = payload.get("failedTests", 0)
        tc_title = payload.get("testcaseTitle", "")
        language = payload.get("language", "python")

        system_prompt = (
            "You are a friendly, precise Python debugging tutor. "
            "A student ran their activity and encountered errors or failing testcases. "
            "Analyze the failure and explain:\n"
            "1. Exactly what went wrong (in clear, beginner-friendly terms).\n"
            "2. The root cause (e.g. off-by-one, wrong return type, syntax error, condition flipped).\n"
            "3. The next actionable step to fix it.\n\n"
            "Guidelines:\n"
            "- Keep explanation between 2 to 4 sentences.\n"
            "- Use clean Markdown and inline code tags.\n"
            "- Be constructive and encouraging."
        )

        user_content_parts = [
            f"**Activity Type**: `{act_type}` (Language: `{language}`)",
        ]

        if tc_title:
            user_content_parts.append(f"**Failing Testcase**: {tc_title}")

        if failed_count:
            user_content_parts.append(f"**Failed Tests Count**: {failed_count} of {len(tests)}")

        if stderr:
            user_content_parts.append(f"\n**Execution Error / Traceback**:\n```\n{stderr}\n```")

        if code:
            user_content_parts.append(f"\n**Student Code**:\n```python\n{code}\n```")

        if tests:
            test_summary = "\n".join(
                f"- Test '{t.get('title', t.get('name', 'Case'))}': passed={t.get('passed', False)}"
                for t in tests[:5]
            )
            user_content_parts.append(f"\n**Testcases Summary**:\n{test_summary}")

        user_content_parts.append(
            "\nProvide helpful, formative feedback diagnosing the failure and advising how to correct it."
        )

        user_prompt = "\n".join(user_content_parts)
        return system_prompt, user_prompt
