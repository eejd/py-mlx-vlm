"""Parse native XML tool calls from MiniCPM5 models.

Format: https://huggingface.co/openbmb/MiniCPM5-2B/blob/main/chat_template.jinja

``<function name="NAME"><param name="KEY">VALUE</param>...</function>``. The chat
template asks the model to wrap a value that holds ``<``, ``&`` or a newline in
``<![CDATA[...]]>``, but the model does not always do it (``<param
name="text">if a < b then <ok> & done</param>``). The call is therefore scanned,
not run through an XML parser: a value is the text up to the next ``</param>``
(or the CDATA block when there is one), so markup characters in it do not make
the call invalid. Differences from the ``xml.etree`` parser this replaced: the
scanner is stricter about text between or after parameters and attributes other
than ``name`` (a ValueError; ElementTree ignored them), and a numeric character
reference that is not a valid XML character stays as written. The quantbench
reference extractor ``minicpm5`` decodes no references at all; the CDATA the chat
template writes is exact in all three.
"""

import ast
import json
import re

tool_call_start = "<function"
tool_call_end = "</function>"

_NAME = r"""(?:"([^"]*)"|'([^']*)')"""
_FUNCTION_OPEN = re.compile(rf"<function\s+name\s*=\s*{_NAME}\s*(/?)>")
_PARAM_OPEN = re.compile(rf"\s*<param\s+name\s*=\s*{_NAME}\s*(/?)>")
_PARAM_END = re.compile(r"</param\s*>")
_FUNCTION_CLOSE = re.compile(r"\s*</function>\s*\Z")
_NAMED_REFERENCES = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'"}
_REFERENCE = re.compile(
    r"&(?:(amp|lt|gt|quot|apos)|#([0-9]{1,7})|#[xX]([0-9a-fA-F]{1,6}));"
)


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


def _decode_reference(match):
    named, decimal, hexadecimal = match.groups()
    if named:
        return _NAMED_REFERENCES[named]
    code = int(decimal) if decimal is not None else int(hexadecimal, 16)
    valid = (
        code in (0x9, 0xA, 0xD)
        or 0x20 <= code <= 0xD7FF
        or 0xE000 <= code <= 0xFFFD
        or 0x10000 <= code <= 0x10FFFF
    )
    return chr(code) if valid else match.group()


def _unescape(text):
    """Decode the XML character references in plain text; anything else is data.

    The five named references and numeric references (at most 7 decimal or 6 hex
    digits) to a valid XML character. An invalid or longer reference stays as written
    where ElementTree rejected the whole call.
    """
    return _REFERENCE.sub(_decode_reference, text) if "&" in text else text


def _read_value(text, pos):
    """Read one parameter value starting after its opening tag; return it and the end.

    Text is data up to ``</param>`` (``</param >`` too); a ``<![CDATA[...]]>`` section
    inside it is exact (no decoding) and may hold ``</param>``. Plain text outside
    CDATA has its character references decoded (``_unescape``). Whitespace is kept
    as written, as ElementTree did.
    """
    parts = []
    close = _PARAM_END.search(text, pos)
    while True:
        if close is not None and close.start() < pos:  # it lay inside a CDATA section
            close = _PARAM_END.search(text, pos)
        limit = close.start() if close is not None else len(text)
        cdata = text.find("<![CDATA[", pos, limit)
        if cdata >= 0:
            parts.append(_unescape(text[pos:cdata]))
            end = text.find("]]>", cdata + len("<![CDATA["))
            if end < 0:
                raise ValueError("Unterminated CDATA in MiniCPM5 parameter.")
            parts.append(text[cdata + len("<![CDATA[") : end])
            pos = end + len("]]>")
            continue
        if close is None:
            raise ValueError("Unterminated MiniCPM5 parameter.")
        parts.append(_unescape(text[pos : close.start()]))
        return "".join(parts), close.end()


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
