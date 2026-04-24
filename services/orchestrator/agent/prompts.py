"""
Dhara AI — Agent System Prompt
Domain-specific instructions for the LLM agent.
"""

from pathlib import Path

_PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "system_prompt.md"

try:
    SYSTEM_PROMPT = _PROMPT_FILE.read_text(encoding="utf-8")
except FileNotFoundError:
    # Fallback for unexpected pathing issues
    SYSTEM_PROMPT = "You are Dhara AI. Generate the feasibility report."




