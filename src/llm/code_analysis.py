"""Code analysis utilities for Daemon.

Provides a JSON schema for code‑analysis LLM responses and a helper to build
the prompt used when the pet is in coding‑assistant mode.
"""

# Minimal schema for a list of issue strings.
CODE_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "issues": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["issues"],
    "additionalProperties": False,
}


def build_code_analysis_prompt(file_path: str, code: str) -> str:
    """Return a prompt that asks the LLM to analyse *code*.

    The prompt includes the file name and the code wrapped in a markdown
    fence. The LLM should return JSON matching ``CODE_ANALYSIS_SCHEMA``.
    """
    return (
        f"You are a ruthless code reviewer. Analyse the contents of the file "
        f"'{file_path}' and list any problems, bugs, or style violations. "
        f"Return a JSON object matching the following schema: {CODE_ANALYSIS_SCHEMA}\n"
        f"```python\n{code}\n```"
    )
