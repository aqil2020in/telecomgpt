"""Bridge ToolRegistry callables to CrewAI / AutoGen tool interfaces."""

from __future__ import annotations

from typing import Any, Callable


# Subsets used by external agent frameworks (keep prompts focused)
CREW_TOOL_NAMES = (
    "hybrid_search",
    "lookup_device",
    "lookup_bands",
    "lookup_glossary",
    "calc_phy",
    "lookup_ca_endc",
    "csv_summary",
    "compare_devices",
)

AUTOGEN_TOOL_NAMES = (
    "hybrid_search",
    "lookup_device",
    "lookup_bands",
    "lookup_glossary",
    "calc_phy",
    "lookup_ca_endc",
    "memory_search",
    "list_kaggle_csvs",
)


def _run_tool(registry: Any, name: str, **kwargs: Any) -> str:
    result = registry.run(name, **kwargs)
    if result.ok:
        out = result.output
        return str(out)[:4000] if out is not None else ""
    return f"Error: {result.error}"


def build_crew_tools(registry: Any, names: tuple[str, ...] = CREW_TOOL_NAMES) -> list[Any]:
    """Build CrewAI BaseTool instances from ToolRegistry."""
    try:
        from crewai.tools import BaseTool
    except ImportError:
        return []

    specs = {s["name"]: s for s in registry.list_specs()}
    tools: list[Any] = []

    for name in names:
        spec = specs.get(name)
        if not spec:
            continue
        desc = spec.get("description", name)
        reg = registry

        class _RegistryTool(BaseTool):
            name: str = name
            description: str = desc

            def _run(self, query: str = "", **kwargs: Any) -> str:
                args = dict(kwargs)
                if query and "query" not in args and "term" not in args and "path" not in args:
                    if name in ("lookup_glossary",):
                        args["term"] = query
                    elif name in ("csv_summary",):
                        args["path"] = query
                    else:
                        args["query"] = query
                return _run_tool(reg, name, **args)

        tools.append(_RegistryTool())
    return tools


def build_autogen_functions(registry: Any, names: tuple[str, ...] = AUTOGEN_TOOL_NAMES) -> list[dict]:
    """Return {name, fn, description} for AutoGen register_function."""
    specs = {s["name"]: s for s in registry.list_specs()}
    fns: list[dict] = []

    for name in names:
        spec = specs.get(name)
        if not spec:
            continue
        desc = spec.get("description", name)

        def make_fn(tool_name: str) -> Callable[..., str]:
            def fn(query: str = "", **kwargs: Any) -> str:
                args = dict(kwargs)
                if query:
                    if tool_name == "lookup_glossary":
                        args.setdefault("term", query)
                    elif tool_name == "csv_summary":
                        args.setdefault("path", query)
                    else:
                        args.setdefault("query", query)
                return _run_tool(registry, tool_name, **args)

            fn.__name__ = tool_name
            fn.__doc__ = desc
            return fn

        fns.append({"name": name, "fn": make_fn(name), "description": desc})
    return fns
