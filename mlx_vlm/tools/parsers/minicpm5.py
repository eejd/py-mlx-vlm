"""Parse native XML tool calls from MiniCPM5 models.

Format: https://huggingface.co/openbmb/MiniCPM5-2B/blob/main/chat_template.jinja

``<function name="NAME"><param name="KEY">VALUE</param>...</function>``. The chat
template asks the model to wrap a value that holds ``<``, ``&`` or a newline in
``<![CDATA[...]]>``, but the model does not always do it (``<param
name="text">if a < b then <ok> & done</param>``). The call is therefore scanned,
not run through an XML parser: a value is the text up to the next ``</param>``
(or the CDATA block when there is one), so markup characters in it do not make
the call invalid.
"""

import ast
import html
import json
import re

tool_call_start = "<function"
tool_call_end = "</function>"

_NAME = r"""(?:"([^"]*)"|'([^']*)')"""
_FUNCTION_OPEN = re.compile(rf"<function\s+name\s*=\s*{_NAME}\s*(/?)>")
_PARAM_OPEN = re.compile(rf"\s*<param\s+name\s*=\s*{_NAME}\s*(/?)>")
_FUNCTION_CLOSE = re.compile(r"\s*</function>\s*\Z")
# The XML character references a model writes instead of CDATA; a bare ``&`` is data.
_ENTITY = re.compile(r"&(?:amp|lt|gt|quot|apos|#[0-9]+|#[xX][0-9a-fA-F]+);")


def _argument_properties(name, tools):
    for tool in tools or []:
        function = tool.get("function") or {}
        if function.get("name") == name:
            return (function.get("parameters") or {}).get("properties", {})
    return {}


def _parse_value(value, schema):
    param_type = schema.get("type") if isinstance(schema, dict) else None
    if param_type == "string" or (
        isinstance(param_type, list) and "string" in param_type
    ):
        return value

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass

    # The chat template also renders Python literals for non-string arguments.
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value


def _name(match):
    return match.group(1) if match.group(1) is not None else match.group(2)


def _read_value(text, pos):
    """Read one parameter value starting after its opening tag; return it and the end.

    Text is data up to ``</param>``; a ``<![CDATA[...]]>`` section inside it is exact
    (no decoding) and may hold ``</param>``. Plain text between sections has its
    well-formed character references decoded.
    """
    parts = []
    while True:
        close = text.find("</param>", pos)
        cdata = text.find("<![CDATA[", pos)
        if cdata >= 0 and (close < 0 or cdata < close):
            parts.append(_unescape(text[pos:cdata]))
            end = text.find("]]>", cdata + len("<![CDATA["))
            if end < 0:
                raise ValueError("Unterminated CDATA in MiniCPM5 parameter.")
            parts.append(text[cdata + len("<![CDATA[") : end])
            pos = end + len("]]>")
            continue
        if close < 0:
            raise ValueError("Unterminated MiniCPM5 parameter.")
        parts.append(_unescape(text[pos:close]))
        return "".join(parts), close + len("</param>")


def _unescape(text):
    return _ENTITY.sub(lambda m: html.unescape(m.group()), text)


def parse_tool_call(text: str, tools=None):
    """Parse a complete function element or the shared server's stripped body."""
    text = text.strip()
    if not text.startswith(tool_call_start):
        # process_tool_calls removes both markers, leaving name="...">...</param>.
        text = f"{tool_call_start} {text}{tool_call_end}"

    opener = _FUNCTION_OPEN.match(text)
    if opener is None:
        raise ValueError("Invalid MiniCPM5 function call.")
    name = (_name(opener) or "").strip()
    if not name:
        raise ValueError("No MiniCPM5 function name provided.")

    properties = _argument_properties(name, tools)
    arguments = {}
    pos = opener.end()
    if opener.group(3):  # <function name="..."/>
        if text[pos:].strip():
            raise ValueError("Invalid MiniCPM5 function call.")
        return {"name": name, "arguments": arguments}

    while (param := _PARAM_OPEN.match(text, pos)) is not None:
        key = _name(param)
        if not key or key in arguments:
            raise ValueError("Invalid MiniCPM5 function parameter.")
        if param.group(3):  # <param name="..."/>
            value, pos = "", param.end()
        else:
            value, pos = _read_value(text, param.end())
        arguments[key] = _parse_value(value, properties.get(key, {}))

    if _FUNCTION_CLOSE.match(text, pos) is None:
        raise ValueError("Invalid MiniCPM5 function parameter.")
    return {"name": name, "arguments": arguments}
