import subprocess
import sys
import tempfile
import os
from typing import Dict, Any, List

class SubmissionEvaluator:
    """Executes or validates Python code submissions against testcases."""

    @staticmethod
    def evaluate(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the submitted Python code against testcases in an isolated temp environment."""
        code = payload.get("code", "")
        testcases: List[Dict[str, Any]] = payload.get("tests", [])

        if not code.strip():
            return {
                "passed": False,
                "tests": [
                    {
                        "name": "Validation",
                        "passed": False,
                        "stdout": "",
                        "stderr": "No code submitted for evaluation.",
                    }
                ],
            }

        # If no testcases provided, run a syntax and compilation check
        if not testcases:
            try:
                compile(code, "<string>", "exec")
                return {
                    "passed": True,
                    "tests": [
                        {
                            "name": "Syntax & Compilation",
                            "passed": True,
                            "stdout": "Code compiled cleanly.",
                            "stderr": "",
                        }
                    ],
                }
            except Exception as e:
                return {
                    "passed": False,
                    "tests": [
                        {
                            "name": "Syntax & Compilation",
                            "passed": False,
                            "stdout": "",
                            "stderr": str(e),
                        }
                    ],
                }

        results = []
        all_passed = True

        for i, tc in enumerate(testcases):
            tc_name = tc.get("title") or tc.get("name") or f"Test {i + 1}"
            expected_stdout = tc.get("stdout") or tc.get("expected") or ""
            stdin_data = tc.get("stdin") or tc.get("input") or ""
            if isinstance(stdin_data, list):
                stdin_data = "\n".join(str(x) for x in stdin_data)

            # Write code to temp file and execute with Python 3
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
                f.write(code)
                temp_path = f.name

            try:
                proc = subprocess.run(
                    [sys.executable, temp_path],
                    input=str(stdin_data),
                    text=True,
                    capture_output=True,
                    timeout=5,
                )
                actual_stdout = proc.stdout
                actual_stderr = proc.stderr
                exit_code = proc.returncode

                # Compare output ignoring trailing whitespace
                passed = (
                    exit_code == 0
                    and (
                        not expected_stdout
                        or actual_stdout.strip() == expected_stdout.strip()
                    )
                )

                if not passed:
                    all_passed = False

                results.append({
                    "name": tc_name,
                    "passed": passed,
                    "stdout": actual_stdout,
                    "stderr": actual_stderr,
                    "expected": expected_stdout,
                    "actual": actual_stdout,
                })

            except subprocess.TimeoutExpired:
                all_passed = False
                results.append({
                    "name": tc_name,
                    "passed": False,
                    "stdout": "",
                    "stderr": "Execution timed out (5s limit exceeded).",
                    "expected": expected_stdout,
                    "actual": "Timeout",
                })
            except Exception as ex:
                all_passed = False
                results.append({
                    "name": tc_name,
                    "passed": False,
                    "stdout": "",
                    "stderr": str(ex),
                    "expected": expected_stdout,
                    "actual": "Error",
                })
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass

        return {
            "passed": all_passed,
            "tests": results,
        }
