"""AutoGen integration — autonomous tool-calling as a LangGraph specialist agent."""

from __future__ import annotations

import os
from typing import Any


def autogen_available() -> bool:
    try:
        import autogen  # noqa: F401

        return True
    except ImportError:
        return False


def run_autogen_tools(
    query: str,
    tool_specs: list[dict],
    tool_registry: Any,
    *,
    memory_context: str | None = None,
    max_rounds: int = 4,
) -> dict:
    """Run AutoGen assistant + user proxy with ToolRegistry functions."""
    if not autogen_available():
        from ..react_loop import run_react_tools

        out = run_react_tools(query, tool_specs, tool_registry)
        out["engine"] = "react_fallback"
        out["agent"] = "autogen"
        out["autogen_installed"] = False
        return out

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        from ..react_loop import run_react_tools

        out = run_react_tools(query, tool_specs, tool_registry)
        out["engine"] = "react_fallback"
        out["agent"] = "autogen"
        out["note"] = "AutoGen requires OPENAI_API_KEY; used ReAct fallback."
        return out

    try:
        import autogen
        from autogen import AssistantAgent, UserProxyAgent

        from .tool_bridge import _run_tool, build_autogen_functions

        model = os.environ.get("TELECOMGPT_MODEL", "gpt-4o-mini")
        llm_config = {
            "config_list": [{"model": model, "api_key": api_key}],
            "temperature": 0.3,
        }

        ctx = (memory_context or "")[:2000]
        system = (
            "You are TelecomGPT AutoGen assistant for 5G NR / LTE engineering. "
            "Use tools to answer precisely. Cite bands and specs when relevant.\n"
            f"Memory context:\n{ctx}"
        )

        assistant = AssistantAgent(
            name="telecom_assistant",
            system_message=system,
            llm_config=llm_config,
        )
        user = UserProxyAgent(
            name="telecom_user",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=max_rounds,
            code_execution_config=False,
            llm_config=llm_config,
        )

        tool_calls: list[dict] = []
        for item in build_autogen_functions(tool_registry):
            name = item["name"]
            desc = item["description"]
            reg = tool_registry

            def make_fn(tool_name: str, tool_desc: str):
                def fn(query: str) -> str:
                    args: dict = {}
                    if tool_name == "lookup_glossary":
                        args["term"] = query
                    elif tool_name == "csv_summary":
                        args["path"] = query
                    else:
                        args["query"] = query
                    try:
                        out = _run_tool(reg, tool_name, **args)
                        tool_calls.append({"tool": tool_name, "ok": True, "output": str(out)[:400]})
                        return str(out)
                    except Exception as ex:
                        tool_calls.append({"tool": tool_name, "ok": False, "error": str(ex)[:200]})
                        return f"Error: {ex}"

                fn.__name__ = tool_name
                fn.__doc__ = tool_desc
                return fn

            fn = make_fn(name, desc)
            autogen.register_function(
                fn,
                caller=assistant,
                executor=user,
                name=name,
                description=desc,
            )

        user.initiate_chat(assistant, message=query, max_turns=max_rounds)
        last = ""
        for msg in reversed(user.chat_messages.get(assistant, [])):
            if msg.get("role") == "assistant" or msg.get("name") == "telecom_assistant":
                last = msg.get("content", "")
                if last:
                    break
        if not last and user.chat_messages.get(assistant):
            last = user.chat_messages[assistant][-1].get("content", "")

        summary = "\n".join(
            f"- {t['tool']}: {t.get('output', t.get('error', ''))[:300]}"
            for t in tool_calls
            if t.get("ok")
        )
        content = last.strip() or summary

        return {
            "agent": "autogen",
            "engine": "autogen",
            "content": content,
            "tool_calls": tool_calls,
            "autogen_installed": True,
        }
    except Exception as e:
        from ..react_loop import run_react_tools

        out = run_react_tools(query, tool_specs, tool_registry)
        out["engine"] = "react_fallback"
        out["agent"] = "autogen"
        out["autogen_error"] = str(e)[:300]
        return out
