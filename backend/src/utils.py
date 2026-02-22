"""Utilities for task parsing and LLM requests."""
from openai import OpenAI
import os
from dotenv import load_dotenv
import json
from collections import deque

load_dotenv()


def llm_request(
    model_id: str = None,
    messages: list = None,
    remote: bool = True
) -> str:
    if remote:
        client = OpenAI(
            api_key=os.environ.get("LLM_API_KEY", ""),
            base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
        )
        response = client.chat.completions.create(
            model=model_id or os.environ.get("LLM_MODEL_ID", "gpt-4"),
            messages=messages,
            temperature=0.1
        )
        return response.choices[0].message.content
    return ""


def find_task(s: str) -> str:
    """Extract JSON task list from LLM response."""
    start = s.find("[")
    end = s.rfind("]")
    if start == -1 or end == -1:
        return "[]"
    res = s[start:end + 1]
    return res.replace("\n", "")


def find_json(s: str) -> str:
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1:
        return "{}"
    return s[start:end + 1].replace("\n", "")
