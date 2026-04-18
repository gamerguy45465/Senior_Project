import ast
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    from smolagents import CodeAgent, OpenAIServerModel
    from model import get_tools
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openai"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dotenv"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "smolagents"])
    from dotenv import load_dotenv
    from smolagents import CodeAgent, OpenAIServerModel
    from model import get_tools


DEFAULT_MODEL = "gpt-5-codex"
REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_FILE_BYTES = 100_000
MAX_TOTAL_CONTEXT_CHARS = 22_000
DEFAULT_SMOLAGENTS_FALLBACK_MODEL = "gpt-4.1"
MAX_TEMPLATE_IMAGES_FOR_PROMPT = 8
MAX_TEMPLATE_ANALYSIS_CHARS = 8_000
MAX_TEMPLATE_EMBED_BYTES = 5_000_000
REACT_PLANNING_INTERVAL = 1
REACT_MAX_STEPS = 20
RESPONSES_ONLY_MODEL_PREFIXES = (
    "gpt-5",
    "o1",
    "o3",
    "o4",
)

MIN_TEMPLATE_WINDOW_WIDTH = 420
MAX_TEMPLATE_WINDOW_WIDTH = 1600
MIN_TEMPLATE_WINDOW_HEIGHT = 300
MAX_TEMPLATE_WINDOW_HEIGHT = 1200
MAX_TEMPLATE_ACTION_BUTTONS = 4
MAX_SOURCE_FILE_CONTEXT_CHARS = 9_000
MAX_AUX_FILE_LISTING = 30
MAX_FORM_ITEMS = 40
MAX_FORM_ITEM_CHARS = 120
GENERIC_WINDOW_TITLES = {
    "generated interface",
    "hello app",
    "hello world",
    "app",
}
GENERIC_WIDGET_HINTS = (
    "click me",
    "type here",
    "action 1",
    "action 2",
    "hello app",
)


def clamp_int(value, minimum, maximum):
    return max(int(minimum), min(int(maximum), int(value)))


def _settings_roots():
    roots = []
    if os.name == "nt":
        appdata = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
        if appdata:
            roots.append(os.path.join(appdata, "QtProject", "Text Editor"))
    elif sys.platform == "darwin":
        home = os.path.expanduser("~")
        roots.append(os.path.join(home, "Library", "Application Support", "QtProject", "Text Editor"))
        roots.append(os.path.join(home, "Library", "Preferences", "QtProject", "Text Editor"))
    else:
        xdg_config = os.getenv("XDG_CONFIG_HOME")
        if xdg_config:
            roots.append(os.path.join(xdg_config, "QtProject", "Text Editor"))
        roots.append(os.path.join(os.path.expanduser("~"), ".config", "QtProject", "Text Editor"))

    roots.append(os.path.dirname(os.path.abspath(__file__)))
    return roots


def load_selected_model(default_model=DEFAULT_MODEL):
    env_model = os.getenv("TEXTEDITOR_AI_MODEL", "").strip()
    if env_model:
        return env_model

    for root in _settings_roots():
        settings_path = os.path.join(root, "ai_settings.json")
        try:
            with open(settings_path, "r", encoding="utf-8") as settings_file:
                payload = json.load(settings_file)
        except FileNotFoundError:
            continue
        except (OSError, json.JSONDecodeError):
            continue

        selected_model = str(payload.get("model", "")).strip()
        if selected_model:
            return selected_model

    return default_model


def load_api_key():
    key_name = "OPENAI_API_KEY"
    load_dotenv()
    api_key = os.getenv(key_name)

    if not api_key:
        message = (
            f"Error: {key_name} is not set."
            f" Please ensure that you have a proper API key from OpenAI."
            f" For more information, please go to: https://openai.com/api/"
        )
        raise ValueError(message)

    return api_key


def configure_console_output_encoding():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _load_int_setting(name, default_value, minimum, maximum):
    raw = os.getenv(name, "").strip()
    if not raw:
        return default_value
    try:
        parsed = int(raw)
    except ValueError:
        return default_value
    return max(int(minimum), min(int(maximum), parsed))


def load_react_max_steps():
    return _load_int_setting("TEXTEDITOR_REACT_MAX_STEPS", REACT_MAX_STEPS, 4, 80)


def load_react_planning_interval():
    return _load_int_setting("TEXTEDITOR_REACT_PLANNING_INTERVAL", REACT_PLANNING_INTERVAL, 1, 8)


def resolve_smolagents_model(model_name):
    selected = (model_name or "").strip() or DEFAULT_MODEL
    fallback = os.getenv("TEXTEDITOR_SMOLAGENTS_FALLBACK_MODEL", DEFAULT_SMOLAGENTS_FALLBACK_MODEL).strip()
    fallback = fallback or DEFAULT_SMOLAGENTS_FALLBACK_MODEL
    normalized = selected.lower()

    if any(normalized.startswith(prefix) for prefix in RESPONSES_ONLY_MODEL_PREFIXES):
        return fallback, (
            f"Selected model '{selected}' is Responses-only for this SDK path. "
            f"Using chat-compatible fallback '{fallback}' for SmolAgents."
        )

    return selected, None


def build_reasoning_agent(model_name, tools=None):
    api_key = load_api_key()
    resolved_model, warning = resolve_smolagents_model(model_name)
    react_planning_interval = load_react_planning_interval()
    react_max_steps = load_react_max_steps()
    if warning:
        print(warning)

    model = OpenAIServerModel(
        model_id=resolved_model,
        api_key=api_key,
    )
    agent_tools = tools if tools is not None else get_tools()
    return CodeAgent(
        tools=agent_tools,
        model=model,
        planning_interval=react_planning_interval,
        max_steps=react_max_steps,
    )


def resolve_source_file(raw_path):
    raw = (raw_path or "").strip()
    if not raw:
        raise FileNotFoundError("TEXTEDITOR_ACTIVE_FILE was not provided.")

    candidate_paths = []

    if raw.startswith(("/", "\\")):
        candidate_paths.append((REPO_ROOT / raw.lstrip("/\\")).resolve())

    requested = Path(raw).expanduser()
    candidate_paths.append(requested.resolve())

    if requested.is_absolute() and len(requested.parts) > 1:
        relative_from_root = Path(*requested.parts[1:])
        candidate_paths.append((REPO_ROOT / relative_from_root).resolve())

    candidate_paths.append((REPO_ROOT / requested).resolve())

    seen = set()
    for candidate in candidate_paths:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists() and candidate.is_file():
            return candidate

    raise FileNotFoundError(
        "Active source file not found. "
        f"Expected TEXTEDITOR_ACTIVE_FILE='{raw}' to point to an existing file."
    )


def collect_png_files(directory: Path) -> list:
    if not directory.exists() or not directory.is_dir():
        return []

    png_paths = []
    for root, _dirs, files in os.walk(directory):
        root_path = Path(root)
        for file_name in files:
            if file_name.lower().endswith(".png"):
                png_paths.append((root_path / file_name).resolve())

    return sorted({path for path in png_paths})


def discover_templates_directory(source_file):
    source_dir = source_file.parent.resolve()
    env_template_dir = os.getenv("TEXTEDITOR_TEMPLATE_DIR", "").strip()

    candidates = []
    if env_template_dir:
        candidates.append(Path(env_template_dir).expanduser())

    candidates.append(source_dir / "Templates")
    candidates.append(source_dir.parent / "Templates")
    candidates.append(source_dir.parent.parent / "Templates")
    candidates.append((REPO_ROOT / "Templates").resolve())

    unique_candidates = []
    seen_keys = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        key = str(resolved).lower() if os.name == "nt" else str(resolved)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_candidates.append(resolved)

    existing_template_dirs = []
    for directory in unique_candidates:
        if not directory.exists() or not directory.is_dir():
            continue

        existing_template_dirs.append(directory)
        png_paths = collect_png_files(directory)
        if png_paths:
            return directory, png_paths

    if existing_template_dirs:
        return existing_template_dirs[0], []

    return unique_candidates[0], []


def resolve_templates_directory(source_file):
    template_dir, _pngs = discover_templates_directory(source_file)
    return template_dir


def _truncate_json_payload(payload, limit=MAX_TEMPLATE_ANALYSIS_CHARS):
    serialized = json.dumps(payload, indent=2)
    if len(serialized) <= limit:
        return serialized

    return serialized[:limit] + "\n... (truncated to keep prompt size bounded)"


def _compact_original_analysis(entries):
    compact = []
    if not isinstance(entries, list):
        return compact

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        compact.append(
            {
                "path": entry.get("path"),
                "exists": entry.get("exists"),
                "width": entry.get("width"),
                "height": entry.get("height"),
                "aspect_ratio": entry.get("aspect_ratio"),
                "analysis_mode": entry.get("analysis_mode"),
            }
        )
    return compact


def _compact_processed_analysis(entries):
    compact = []
    if not isinstance(entries, list):
        return compact

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        regions = entry.get("regions")
        role_counts = {}
        if isinstance(regions, list):
            for region in regions:
                if not isinstance(region, dict):
                    continue
                role = str(region.get("role", "unknown"))
                role_counts[role] = int(role_counts.get(role, 0)) + 1

        compact.append(
            {
                "path": entry.get("path"),
                "exists": entry.get("exists"),
                "width": entry.get("width"),
                "height": entry.get("height"),
                "aspect_ratio": entry.get("aspect_ratio"),
                "region_count": entry.get("region_count"),
                "edge_density": entry.get("edge_density"),
                "role_counts": role_counts,
                "analysis_mode": entry.get("analysis_mode"),
            }
        )
    return compact


def build_template_context(source_file):
    templates_dir, discovered_pngs = discover_templates_directory(source_file)
    os.environ["TEXTEDITOR_TEMPLATE_DIR"] = str(templates_dir)

    sections = [f"Template directory selected: {templates_dir}"]

    if not templates_dir.exists() or not templates_dir.is_dir():
        sections.append("Templates directory was not found.")
        return "\n".join(sections), 0, [], [], templates_dir, []

    tools_by_name = {tool.name: tool for tool in get_tools()}
    locate_tool = tools_by_name.get("locate_in_templates_directory")
    read_original_tool = tools_by_name.get("read_original_pngs")
    read_processed_tool = tools_by_name.get("read_pngs")

    tool_png_paths = []
    if locate_tool is not None:
        try:
            tool_png_paths = locate_tool.forward("")
        except Exception as exc:
            sections.append(f"locate_in_templates_directory failed: {exc}")

    normalized_pngs = sorted(
        {
            str(Path(path).resolve())
            for path in tool_png_paths
            if str(path).strip().lower().endswith(".png")
        }
        | {str(path.resolve()) for path in discovered_pngs}
    )

    total_pngs = len(normalized_pngs)
    if total_pngs == 0:
        sections.append("Templates directory exists, but no PNG files were found.")
        return "\n".join(sections), 0, [], [], templates_dir, []

    sections.append(f"Template PNG files found: {total_pngs}")
    for path in normalized_pngs[:MAX_TEMPLATE_IMAGES_FOR_PROMPT]:
        sections.append(f"- {path}")
    if total_pngs > MAX_TEMPLATE_IMAGES_FOR_PROMPT:
        sections.append(f"- ... plus {total_pngs - MAX_TEMPLATE_IMAGES_FOR_PROMPT} additional PNG files")

    limited_pngs = normalized_pngs[:MAX_TEMPLATE_IMAGES_FOR_PROMPT]

    original_analysis = []
    if read_original_tool is None:
        sections.append("read_original_pngs tool is unavailable in python/model.py.")
    else:
        try:
            original_analysis = read_original_tool.forward(limited_pngs)
        except Exception as exc:
            sections.append(f"read_original_pngs failed: {exc}")

    processed_analysis = []
    if read_processed_tool is None:
        sections.append("read_pngs tool is unavailable in python/model.py.")
    else:
        try:
            processed_analysis = read_processed_tool.forward(limited_pngs)
        except Exception as exc:
            sections.append(f"read_pngs failed: {exc}")

    compact_original = _compact_original_analysis(original_analysis)
    compact_processed = _compact_processed_analysis(processed_analysis)

    sections.append("Original Template summary (PRIMARY source):")
    sections.append("```json")
    sections.append(_truncate_json_payload(compact_original))
    sections.append("```")

    sections.append("Processed Template summary from read_pngs (SECONDARY source):")
    sections.append("```json")
    sections.append(_truncate_json_payload(compact_processed))
    sections.append("```")

    return (
        "\n".join(sections),
        total_pngs,
        original_analysis,
        processed_analysis,
        templates_dir,
        normalized_pngs,
    )


def select_agent_tools(template_png_count):
    tools = get_tools()
    if template_png_count <= 0:
        return tools

    allowed = {
        "locate_in_templates_directory",
        "read_original_pngs",
        "read_pngs",
    }
    filtered = [tool for tool in tools if tool.name in allowed]
    return filtered or tools


def build_project_context(project_dir, source_file):
    sections = [f"Project root: {project_dir}", f"Primary file: {source_file.name}"]

    try:
        source_content = source_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        source_content = ""

    if source_content:
        clipped = source_content[:MAX_SOURCE_FILE_CONTEXT_CHARS]
        if len(source_content) > MAX_SOURCE_FILE_CONTEXT_CHARS:
            clipped += "\n# ... truncated source context ..."
        sections.append(f"\n\n### {source_file.name}\n```text\n{clipped}\n```")

    sibling_files = []
    try:
        for file_path in sorted(project_dir.glob("*.py")):
            if file_path.resolve() == source_file.resolve():
                continue
            sibling_files.append(file_path.name)
            if len(sibling_files) >= MAX_AUX_FILE_LISTING:
                break
    except OSError:
        sibling_files = []

    if sibling_files:
        sections.append("\n\nOther Python files in this folder:")
        for file_name in sibling_files:
            sections.append(f"- {file_name}")

    text = "".join(sections)
    if len(text) > MAX_TOTAL_CONTEXT_CHARS:
        text = text[:MAX_TOTAL_CONTEXT_CHARS] + "\n... (truncated project context) ..."
    return text


def infer_projects_subdirectory(source_file):
    projects_root = (REPO_ROOT / "Projects").resolve()
    try:
        relative_path = source_file.resolve().relative_to(projects_root)
    except ValueError:
        return None

    relative_parent = relative_path.parent.as_posix()
    if relative_parent in ("", "."):
        return source_file.parent.name
    return relative_parent


def normalize_form_items(form_items):
    cleaned_items = []
    seen = set()
    for raw_item in form_items or []:
        text = str(raw_item or "").strip()
        text = re.sub(r"\s+", " ", text)
        if not text:
            continue
        text = text[:MAX_FORM_ITEM_CHARS]
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned_items.append(text)
        if len(cleaned_items) >= MAX_FORM_ITEMS:
            break
    return cleaned_items


def build_form_requirement_text(form_items):
    cleaned_items = normalize_form_items(form_items)

    base_rule = (
        "Requirement: if a function has a decorator @form (case-insensitive), inspect the function directly below "
        "that decorator, extract literal string items, and render them as a visible selectable GTK list widget."
    )
    if not cleaned_items:
        return base_rule

    serialized_items = ", ".join(json.dumps(item) for item in cleaned_items)
    return (
        f"{base_rule}\n"
        f"Requirement: use these extracted @form items in order: [{serialized_items}]."
    )


def build_generation_task(source_file, output_file, project_context, template_context, template_png_count, form_items=None):
    form_requirement = build_form_requirement_text(form_items)
    projects_hint = infer_projects_subdirectory(source_file)
    if projects_hint:
        tool_hint = (
            "Tool hint: if you need to call locate_python_files, use this query first: "
            f"'{projects_hint}'."
        )
    else:
        tool_hint = (
            "Tool hint: locate_python_files expects a subdirectory inside ../Projects."
        )

    if template_png_count > 0:
        template_hint = (
            "Template requirement: template PNGs were found.\n"
            "PRIMARY source rule: use the ORIGINAL image information from read_original_pngs as the main truth for "
            "layout, spacing, and visual hierarchy.\n"
            "SECONDARY source rule: use read_pngs processed analysis only to refine region boundaries.\n"
            "ReAct requirement: follow iterative Thought -> Action -> Observation steps before final answer.\n"
            "Mandatory tool sequence before final code: "
            "1) locate_in_templates_directory, 2) read_original_pngs, 3) read_pngs.\n"
            "Output GTK code that mirrors the original template image dimensions and composition.\n"
            "Template-first text rule: do NOT inject source-derived @Header/@output text overlays unless the text is "
            "visually supported by template evidence."
        )
        source_behavior_requirements = (
            "Requirement: if a function has a decorator @resize (case-insensitive), the main GTK window may be "
            "resizable.\n"
            f"{form_requirement}"
        )
    else:
        template_hint = (
            "Template requirement: no template PNGs were found in the available Templates directories. "
            "Fallback to source code context for layout decisions."
        )
        source_behavior_requirements = (
            "Requirement: if a function has a decorator @Header (case-insensitive), extract the first literal "
            "string from that function's print(...) or return statement and render it as the GTK header text.\n"
            "Requirement: if there is a decorator @output \"Hello World\", remove that "
            "decorator usage and render the same text in a GTK text widget.\n"
            "Requirement: if a function has a decorator @resize (case-insensitive), the main GTK window must be "
            "resizable.\n"
            f"{form_requirement}"
        )
    tool_safety_hint = (
        "Tool safety rule: in ReAct actions, do not call open(), read_text(), write_text(), or any direct "
        "filesystem I/O; use only the provided tools from python/model.py."
    )
    reasoning_depth_hint = (
        "Reasoning depth requirement: when tools are available, perform multiple Thought -> Action -> Observation "
        "cycles before final code."
    )

    return (
        f"Task: Generate a GTK GUI for {source_file.name}.\n"
        f"Write the result as a standalone Python module for a new file named {output_file.name}.\n"
        f"{source_behavior_requirements}\n"
        f"{template_hint}\n"
        f"{tool_safety_hint}\n"
        f"{reasoning_depth_hint}\n"
        "You already have access to tools from python/model.py. Use them when needed.\n"
        f"{tool_hint}\n"
        "Return only the resulting Python code.\n\n"
        "### Template Context\n"
        f"{template_context}\n\n"
        "### Project Context\n"
        f"{project_context}"
    )


def extract_python_code(raw_text):
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("Model response was empty.")

    fence = "```"
    start = text.find(fence)
    while start != -1:
        line_end = text.find("\n", start)
        if line_end == -1:
            break

        end = text.find(fence, line_end + 1)
        if end == -1:
            break

        candidate = text[line_end + 1 : end].strip()
        if candidate:
            return candidate

        start = text.find(fence, end + len(fence))

    return text


def choose_output_file(source_file):
    requested_name = os.getenv("TEXTEDITOR_TARGET_FILE", "").strip()
    source_directory = source_file.parent.resolve()

    if requested_name:
        target_path = Path(requested_name)
        if target_path.is_absolute():
            raise ValueError("TEXTEDITOR_TARGET_FILE must be a file name, not an absolute path.")
        if target_path.parent not in (Path(""), Path(".")):
            raise ValueError("TEXTEDITOR_TARGET_FILE must not include directories.")
        return source_directory / target_path.name

    base_name = f"{source_file.stem}_generated"
    candidate = source_directory / f"{base_name}.py"
    counter = 1
    while candidate.exists():
        candidate = source_directory / f"{base_name}_{counter}.py"
        counter += 1
    return candidate


def write_generated_code(output_file, generated_code):
    output_file.parent.mkdir(parents=True, exist_ok=True)

    backup_file = None
    if output_file.exists():
        backup_file = output_file.with_suffix(output_file.suffix + ".bak")
        backup_file.write_text(output_file.read_text(encoding="utf-8"), encoding="utf-8")

    normalized = generated_code.rstrip() + "\n"
    output_file.write_text(normalized, encoding="utf-8")
    return output_file, backup_file


def coerce_agent_output_text(agent_result):
    if isinstance(agent_result, dict):
        dict_output = agent_result.get("output")
        if dict_output is not None:
            return str(dict_output)

    output_attr = getattr(agent_result, "output", None)
    if output_attr is not None:
        return str(output_attr)

    return str(agent_result)


def looks_like_gtk_code(code_text):
    text = (code_text or "")
    lowered = text.lower()
    return (
        "gi.require_version(\"gtk\"" in lowered
        or "from gi.repository import gtk" in lowered
        or "gtk.applicationwindow" in lowered
    )


def _normalize_text_token(value):
    text = str(value or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def _template_strict_mode_enabled():
    value = _normalize_text_token(os.getenv("TEXTEDITOR_TEMPLATE_STRICT", "1"))
    return value not in {"0", "false", "no", "off"}


def _code_references_selected_template(code_text, selected_template):
    lowered = str(code_text or "").lower()
    if not lowered:
        return False

    if "gtk.image.new_from_file" in lowered and ".png" in lowered:
        return True

    path = ""
    if isinstance(selected_template, dict):
        path = str(selected_template.get("path", "") or "").strip()

    if not path:
        return False

    normalized_path = path.replace("\\", "/").lower()
    file_name = Path(path).name.lower()
    stem = Path(path).stem.lower()

    return (
        (normalized_path and normalized_path in lowered)
        or (file_name and file_name in lowered)
        or (stem and stem in lowered)
    )


def _code_looks_generic(code_text):
    lowered = str(code_text or "").lower()
    if not lowered:
        return True

    hint_hits = sum(1 for hint in GENERIC_WIDGET_HINTS if hint in lowered)
    return hint_hits >= 2


def _code_uses_template_overlay_chrome(code_text):
    lowered = str(code_text or "").lower()
    if not lowered:
        return False

    noisy_widget_patterns = (
        "gtk.entry(",
        "gtk.textview(",
        "gtk.scrolledwindow(",
        "gtk.frame(",
        "gtk.button(",
        "action 1",
        "action 2",
        "navigation",
    )
    return any(pattern in lowered for pattern in noisy_widget_patterns)


def should_fallback_to_template_synthesis(generated_code, template_png_count, selected_template):
    if template_png_count <= 0:
        return False

    if not looks_like_gtk_code(generated_code):
        return True

    references_template = _code_references_selected_template(generated_code, selected_template)
    lowered = str(generated_code or "").lower()
    template_is_simple = True
    if isinstance(selected_template, dict):
        template_is_simple = int(selected_template.get("region_count", 0) or 0) <= 2

    if _template_strict_mode_enabled():
        if not references_template:
            return True

        # Strict mode rejects generic/chrome-heavy output for simple templates.
        if template_is_simple and _code_uses_template_overlay_chrome(generated_code):
            return True

        # For simple templates, reject extra top-left header overlays over a template image.
        if template_is_simple and "overlay.add_overlay(header)" in lowered:
            return True

        return False

    if references_template:
        return False

    return _code_looks_generic(generated_code)


def is_context_length_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "context_length_exceeded" in text or "maximum context length" in text


def _decorator_name(node):
    candidate = node.func if isinstance(node, ast.Call) else node
    if isinstance(candidate, ast.Name):
        return str(candidate.id or "").strip().lower()
    if isinstance(candidate, ast.Attribute):
        return str(candidate.attr or "").strip().lower()
    return ""


def _extract_constant_string(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        value = node.value.strip()
        if value:
            return value
    return None


def _extract_string_from_header_function(function_node):
    for node in ast.walk(function_node):
        if isinstance(node, ast.Call):
            if _decorator_name(node.func) != "print":
                continue
            for arg in node.args:
                value = _extract_constant_string(arg)
                if value:
                    return value
        elif isinstance(node, ast.Return):
            value = _extract_constant_string(node.value)
            if value:
                return value
    return None


def _extract_header_text_from_content(content):
    try:
        tree = ast.parse(content)
    except SyntaxError:
        tree = None

    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            for decorator in node.decorator_list:
                if _decorator_name(decorator) != "header":
                    continue

                if isinstance(decorator, ast.Call):
                    for arg in decorator.args:
                        value = _extract_constant_string(arg)
                        if value:
                            return value[:240]

                value = _extract_string_from_header_function(node)
                if value:
                    return value[:240]

    inline_pattern = r"@header\s*(?:\(\s*(['\"])(?P<call_value>.*?)\1\s*\)|\s+(['\"])(?P<line_value>.*?)\3)"
    inline_match = re.search(inline_pattern, content, flags=re.IGNORECASE | re.DOTALL)
    if inline_match:
        value = (inline_match.group("call_value") or inline_match.group("line_value") or "").strip()
        if value:
            return value[:240]

    header_marker = re.search(r"@header\b", content, flags=re.IGNORECASE)
    if header_marker:
        remainder = content[header_marker.end() :]
        fallback_patterns = [
            r"print\(\s*(['\"])(?P<value>.*?)\1\s*\)",
            r"return\s+(['\"])(?P<value>.*?)\1",
        ]
        for pattern in fallback_patterns:
            fallback_match = re.search(pattern, remainder, flags=re.IGNORECASE | re.DOTALL)
            if not fallback_match:
                continue
            value = (fallback_match.group("value") or "").strip()
            if value:
                return value[:240]

    return None


def extract_header_text_from_source(source_file):
    try:
        content = source_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    return _extract_header_text_from_content(content)


def _source_requests_resizable_window_from_content(content):
    try:
        tree = ast.parse(content)
    except SyntaxError:
        tree = None

    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for decorator in node.decorator_list:
                if _decorator_name(decorator) == "resize":
                    return True

    return re.search(r"@resize\b", content, flags=re.IGNORECASE) is not None


def source_requests_resizable_window(source_file):
    try:
        content = source_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    return _source_requests_resizable_window_from_content(content)


def _normalize_form_item(value):
    text = str(value or "").strip()
    if not text:
        return None
    text = re.sub(r"\s+", " ", text)
    return text[:MAX_FORM_ITEM_CHARS]


def _append_unique_form_items(target_items, candidates):
    seen = {str(item).lower() for item in target_items}
    for candidate in candidates or []:
        normalized = _normalize_form_item(candidate)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        target_items.append(normalized)
        seen.add(key)
        if len(target_items) >= MAX_FORM_ITEMS:
            break
    return target_items


def _extract_string_items_from_node(node):
    if node is None:
        return []

    single_value = _extract_constant_string(node)
    if single_value:
        return [single_value]

    values = []
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for element in node.elts:
            element_value = _extract_constant_string(element)
            if element_value:
                values.append(element_value)
        return values

    if isinstance(node, ast.Dict):
        for value_node in node.values:
            element_value = _extract_constant_string(value_node)
            if element_value:
                values.append(element_value)
        return values

    if isinstance(node, ast.Call):
        call_name = _decorator_name(node.func)
        if call_name in {"list", "tuple", "set"} and node.args:
            return _extract_string_items_from_node(node.args[0])

    return values


def _extract_form_items_from_function(function_node):
    items = []

    for statement in function_node.body:
        if isinstance(statement, ast.Assign):
            _append_unique_form_items(items, _extract_string_items_from_node(statement.value))
        elif isinstance(statement, ast.AnnAssign):
            _append_unique_form_items(items, _extract_string_items_from_node(statement.value))
        elif isinstance(statement, ast.Return):
            _append_unique_form_items(items, _extract_string_items_from_node(statement.value))
        elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            call_name = _decorator_name(call.func)
            if call_name == "append":
                for arg in call.args:
                    _append_unique_form_items(items, _extract_string_items_from_node(arg))
            elif call_name == "extend" and call.args:
                _append_unique_form_items(items, _extract_string_items_from_node(call.args[0]))

        if len(items) >= MAX_FORM_ITEMS:
            return items[:MAX_FORM_ITEMS]

    return items


def _extract_form_items_from_content(content):
    try:
        tree = ast.parse(content)
    except SyntaxError:
        tree = None

    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            has_form_decorator = False
            items = []
            for decorator in node.decorator_list:
                if _decorator_name(decorator) != "form":
                    continue
                has_form_decorator = True
                if isinstance(decorator, ast.Call):
                    for arg in decorator.args:
                        _append_unique_form_items(items, _extract_string_items_from_node(arg))

            if not has_form_decorator:
                continue

            _append_unique_form_items(items, _extract_form_items_from_function(node))
            if items:
                return items[:MAX_FORM_ITEMS]

            # If we found @form but no parseable literals, stop early to avoid
            # collecting unrelated assignments elsewhere in the file.
            return []

    form_marker = re.search(r"@form\b", content, flags=re.IGNORECASE)
    if not form_marker:
        return []

    remainder = content[form_marker.end() :]
    matches = re.finditer(
        r"(?m)^\s*[A-Za-z_]\w*\s*=\s*(['\"])(?P<value>.*?)\1\s*$",
        remainder,
    )
    items = []
    for match in matches:
        value = _normalize_form_item(match.group("value"))
        if not value:
            continue
        _append_unique_form_items(items, [value])
        if len(items) >= MAX_FORM_ITEMS:
            break
    return items


def extract_form_items_from_source(source_file):
    try:
        content = source_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    return _extract_form_items_from_content(content)


def extract_output_text_from_source(source_file):
    try:
        content = source_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "Generated Interface"

    header_value = _extract_header_text_from_content(content)
    if header_value:
        return header_value

    patterns = [
        r"@output\s+(['\"])(?P<value>.*?)\1",
        r"return\s+(['\"])(?P<value>.*?)\1",
        r"print\(\s*(['\"])(?P<value>.*?)\1\s*\)",
    ]

    for pattern in patterns:
        match = re.search(pattern, content, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        value = (match.group("value") or "").strip()
        if value:
            return value[:240]

    return source_file.stem.replace("_", " ").strip().title() or "Generated Interface"


def apply_resize_directive_to_generated_code(generated_code, should_resize):
    if not should_resize:
        return generated_code

    text = str(generated_code or "")
    if not text:
        return text

    if re.search(r"\bself\.set_resizable\s*\(\s*True\s*\)", text):
        return text

    updated = re.sub(
        r"\bself\.set_resizable\s*\(\s*False\s*\)",
        "self.set_resizable(True)",
        text,
    )
    if updated != text:
        return updated

    line_patterns = (
        re.compile(r"(?m)^(?P<indent>\s*)self\.set_default_size\([^\n]*\)\s*$"),
        re.compile(r"(?m)^(?P<indent>\s*)super\(\).__init__\([^\n]*\)\s*$"),
    )
    for pattern in line_patterns:
        match = pattern.search(text)
        if not match:
            continue
        insertion = f"{match.group(0)}\n{match.group('indent')}self.set_resizable(True)"
        return text[: match.start()] + insertion + text[match.end() :]

    return text


def _build_form_injection_block(form_items, indent):
    item_literal = json.dumps(form_items)
    return "\n".join(
        [
            f"{indent}# @form items injected by texteditor agent",
            f"{indent}form_items = {item_literal}",
            f"{indent}if form_items:",
            f"{indent}    form_frame = Gtk.Frame(label='Items')",
            f"{indent}    form_frame.set_margin_top(10)",
            f"{indent}    form_frame.set_margin_start(10)",
            f"{indent}    form_frame.set_margin_end(10)",
            f"{indent}",
            f"{indent}    form_list = Gtk.ListBox()",
            f"{indent}    form_list.set_selection_mode(Gtk.SelectionMode.SINGLE)",
            f"{indent}    for form_item in form_items:",
            f"{indent}        row = Gtk.ListBoxRow()",
            f"{indent}        row_label = Gtk.Label(label=form_item, xalign=0.0)",
            f"{indent}        row_label.set_margin_top(6)",
            f"{indent}        row_label.set_margin_bottom(6)",
            f"{indent}        row_label.set_margin_start(8)",
            f"{indent}        row_label.set_margin_end(8)",
            f"{indent}        row.add(row_label)",
            f"{indent}        form_list.add(row)",
            f"{indent}    form_frame.add(form_list)",
            f"{indent}",
            f"{indent}    existing_child = self.get_child()",
            f"{indent}    if isinstance(existing_child, Gtk.Box):",
            f"{indent}        existing_child.pack_start(form_frame, False, False, 0)",
            f"{indent}    else:",
            f"{indent}        wrapper_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)",
            f"{indent}        wrapper_box.set_border_width(10)",
            f"{indent}        if existing_child is not None:",
            f"{indent}            self.remove(existing_child)",
            f"{indent}            wrapper_box.pack_start(existing_child, True, True, 0)",
            f"{indent}        wrapper_box.pack_start(form_frame, False, False, 0)",
            f"{indent}        self.add(wrapper_box)",
        ]
    )


def apply_form_directive_to_generated_code(generated_code, form_items):
    cleaned_items = normalize_form_items(form_items)
    if not cleaned_items:
        return generated_code

    text = str(generated_code or "")
    if not text or "Gtk" not in text:
        return text

    marker = "# @form items injected by texteditor agent"
    if marker in text:
        return text

    if "Gtk.ListBox" in text and all(item in text for item in cleaned_items):
        return text

    insertion_match = re.search(r"(?m)^(?P<indent>\s*)self\.add\([^\n]*\)\s*$", text)
    if not insertion_match:
        return text

    insertion = _build_form_injection_block(cleaned_items, insertion_match.group("indent"))
    return text[: insertion_match.end()] + "\n" + insertion + text[insertion_match.end() :]


def pick_primary_template_entry(template_analysis, template_png_paths, source_file=None):
    source_stem = ""
    if source_file is not None:
        source_stem = source_file.stem.lower().strip()

    candidates = []
    if isinstance(template_analysis, list):
        for entry in template_analysis:
            if not isinstance(entry, dict):
                continue
            if not entry.get("exists"):
                continue

            width = entry.get("width")
            height = entry.get("height")
            if not (isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0):
                continue

            path_str = str(entry.get("path", ""))
            path_name = Path(path_str).stem.lower() if path_str else ""
            aspect = float(width) / float(height) if height else 0.0
            area = float(width * height)
            region_count = int(entry.get("region_count", 0) or 0)

            score = 0.0
            score += min(area / 8000.0, 120.0)
            if aspect >= 1.0:
                score += 90.0
            score += max(0.0, 36.0 - (abs(aspect - 1.4) * 24.0))
            score += min(region_count * 2.5, 30.0)

            if source_stem and path_name:
                if source_stem in path_name or path_name in source_stem:
                    score += 220.0

            if "template" in path_name or "mockup" in path_name or "layout" in path_name:
                score += 18.0

            candidates.append((score, entry))

    if candidates:
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return candidates[0][1]

    fallback_path = str(template_png_paths[0]) if template_png_paths else ""
    return {
        "path": fallback_path,
        "exists": bool(fallback_path),
        "width": 960,
        "height": 640,
        "regions": [],
        "region_count": 0,
        "edge_density": 0.0,
        "mean_bgr": [232.0, 232.0, 232.0],
        "analysis_mode": "fallback",
    }


def _template_background_hex(entry):
    mean_bgr = entry.get("mean_bgr")
    if not isinstance(mean_bgr, list) or len(mean_bgr) < 3:
        return "#e6e6e6"

    try:
        b = clamp_int(round(float(mean_bgr[0])), 0, 255)
        g = clamp_int(round(float(mean_bgr[1])), 0, 255)
        r = clamp_int(round(float(mean_bgr[2])), 0, 255)
    except (TypeError, ValueError):
        return "#e6e6e6"

    return f"#{r:02x}{g:02x}{b:02x}"


def _preferred_window_title(output_text, template_image_path):
    value = str(output_text or "").strip()
    return value or "Generated Interface"


def _load_template_image_base64(template_image_path):
    image_path = str(template_image_path or "").strip()
    if not image_path:
        return ""

    path = Path(image_path)
    if not path.exists() or not path.is_file():
        return ""

    try:
        raw_bytes = path.read_bytes()
    except OSError:
        return ""

    if len(raw_bytes) > MAX_TEMPLATE_EMBED_BYTES:
        return ""

    return base64.b64encode(raw_bytes).decode("ascii")


def _build_visual_match_code(
    window_title,
    overlay_text,
    overlay_alignment,
    app_id,
    window_w,
    window_h,
    background_hex,
    template_image_path,
    template_image_b64,
    is_resizable,
):
    return "\n".join(
        [
            "import base64",
            "import hashlib",
            "import os",
            "import sys",
            "",
            "import gi",
            'gi.require_version("Gtk", "3.0")',
            "from gi.repository import Gdk, GdkPixbuf, Gtk",
            "",
            f"WINDOW_BG = {json.dumps(background_hex)}",
            f"TEMPLATE_IMAGE = {json.dumps(template_image_path)}",
            f"TEMPLATE_IMAGE_B64 = {json.dumps(template_image_b64)}",
            f"OVERLAY_TEXT = {json.dumps(overlay_text)}",
            f"OVERLAY_ALIGNMENT = {json.dumps(overlay_alignment)}",
            "",
            "def resolve_template_image():",
            "    if TEMPLATE_IMAGE and os.path.isfile(TEMPLATE_IMAGE):",
            "        return TEMPLATE_IMAGE",
            "",
            "    if not TEMPLATE_IMAGE_B64:",
            "        return ''",
            "",
            "    try:",
            "        cache_dir = os.path.join(os.path.expanduser('~'), '.texteditor_template_cache')",
            "        os.makedirs(cache_dir, exist_ok=True)",
            "        cache_name = hashlib.sha256(TEMPLATE_IMAGE_B64.encode('ascii')).hexdigest() + '.png'",
            "        cache_path = os.path.join(cache_dir, cache_name)",
            "        if not os.path.isfile(cache_path):",
            "            with open(cache_path, 'wb') as cache_file:",
            "                cache_file.write(base64.b64decode(TEMPLATE_IMAGE_B64))",
            "        return cache_path",
            "    except Exception:",
            "        return ''",
            "",
            "class TemplateGeneratedWindow(Gtk.ApplicationWindow):",
            "    def __init__(self, app):",
            f"        super().__init__(application=app, title={json.dumps(window_title)})",
            f"        self.set_default_size({window_w}, {window_h})",
            "        self.set_position(Gtk.WindowPosition.CENTER)",
            f"        self.set_resizable({str(bool(is_resizable))})",
            "",
            "        overlay = Gtk.Overlay()",
            "        overlay.set_hexpand(True)",
            "        overlay.set_vexpand(True)",
            "        self.add(overlay)",
            "",
            "        resolved_template_image = resolve_template_image()",
            "        if resolved_template_image and os.path.isfile(resolved_template_image):",
            "            image = Gtk.Image()",
            "            try:",
            "                pixbuf = GdkPixbuf.Pixbuf.new_from_file(resolved_template_image)",
            f"                scaled = pixbuf.scale_simple({window_w}, {window_h}, GdkPixbuf.InterpType.BILINEAR)",
            "                image.set_from_pixbuf(scaled if scaled is not None else pixbuf)",
            "            except Exception:",
            "                image = Gtk.Image.new_from_file(resolved_template_image)",
            "            overlay.add(image)",
            "        else:",
            "            body = Gtk.EventBox()",
            "            body.set_name('template_body')",
            "            body.set_hexpand(True)",
            "            body.set_vexpand(True)",
            "            overlay.add(body)",
            "",
            "            css = Gtk.CssProvider()",
            "            css.load_from_data((",
            "                '#template_body {'",
            "                '  background-color: ' + WINDOW_BG + ';'",
            "                '}'",
            "            ).encode('utf-8'))",
            "            screen = Gdk.Screen.get_default()",
            "            if screen is not None:",
            "                Gtk.StyleContext.add_provider_for_screen(",
            "                    screen,",
            "                    css,",
            "                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,",
            "                )",
            "",
            "        if OVERLAY_TEXT:",
            "            header = Gtk.Label(label=OVERLAY_TEXT)",
            "            if OVERLAY_ALIGNMENT == 'center':",
            "                header.set_halign(Gtk.Align.CENTER)",
            "                header.set_valign(Gtk.Align.CENTER)",
            "            else:",
            "                header.set_halign(Gtk.Align.START)",
            "                header.set_valign(Gtk.Align.START)",
            "                header.set_margin_start(18)",
            "                header.set_margin_top(14)",
            "            overlay.add_overlay(header)",
            "",
            "class TemplateGeneratedApp(Gtk.Application):",
            "    def __init__(self):",
            f"        super().__init__(application_id={json.dumps(app_id)})",
            "",
            "    def do_activate(self):",
            "        window = self.props.active_window",
            "        if not window:",
            "            window = TemplateGeneratedWindow(self)",
            "        window.present()",
            "",
            "if __name__ == '__main__':",
            "    app = TemplateGeneratedApp()",
            "    app.run(sys.argv)",
        ]
    )


def _normalized_box(region, defaults, window_w, window_h, min_w=80, min_h=36):
    x, y, w, h = defaults
    if isinstance(region, dict):
        x = int(region.get("x", x))
        y = int(region.get("y", y))
        w = int(region.get("width", w))
        h = int(region.get("height", h))

    max_x = max(0, window_w - min_w)
    max_y = max(0, window_h - min_h)
    x = clamp_int(x, 0, max_x)
    y = clamp_int(y, 0, max_y)
    w = clamp_int(w, min_w, max(min_w, window_w - x))
    h = clamp_int(h, min_h, max(min_h, window_h - y))
    return x, y, w, h


def _largest_region_for_roles(regions, roles):
    if not isinstance(regions, list):
        return None

    candidates = []
    for region in regions:
        if not isinstance(region, dict):
            continue
        if region.get("role") not in roles:
            continue
        width = int(region.get("width", 0))
        height = int(region.get("height", 0))
        candidates.append((width * height, region))

    if not candidates:
        return None

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[0][1]


def _detect_center_text_region(regions, window_w, window_h):
    if not isinstance(regions, list) or window_w <= 0 or window_h <= 0:
        return False

    center_x = window_w / 2.0
    center_y = window_h / 2.0
    max_center_distance = max(window_w, window_h) * 0.24

    for region in regions:
        if not isinstance(region, dict):
            continue
        role = str(region.get("role", ""))
        if role not in {"button", "input", "panel", "content"}:
            continue

        x = int(region.get("x", 0))
        y = int(region.get("y", 0))
        w = int(region.get("width", 0))
        h = int(region.get("height", 0))
        if w <= 0 or h <= 0:
            continue

        rx = x + (w / 2.0)
        ry = y + (h / 2.0)
        dist = ((rx - center_x) ** 2 + (ry - center_y) ** 2) ** 0.5
        area_ratio = float(w * h) / float(window_w * window_h)

        if dist <= max_center_distance and 0.008 <= area_ratio <= 0.22:
            return True

    return False


def build_template_driven_code(source_file, output_file, template_analysis, template_png_paths, form_items=None):
    primary = pick_primary_template_entry(
        template_analysis=template_analysis,
        template_png_paths=template_png_paths,
        source_file=source_file,
    )
    form_items = normalize_form_items(form_items if form_items is not None else extract_form_items_from_source(source_file))
    output_text = extract_output_text_from_source(source_file)
    explicit_header_text = extract_header_text_from_source(source_file)
    header_text = explicit_header_text or output_text
    resize_requested = source_requests_resizable_window(source_file)

    raw_w = int(primary.get("width", 960))
    raw_h = int(primary.get("height", 640))
    window_w = clamp_int(raw_w, MIN_TEMPLATE_WINDOW_WIDTH, MAX_TEMPLATE_WINDOW_WIDTH)
    window_h = clamp_int(raw_h, MIN_TEMPLATE_WINDOW_HEIGHT, MAX_TEMPLATE_WINDOW_HEIGHT)

    regions = primary.get("regions")
    if not isinstance(regions, list):
        regions = []
    region_count = int(primary.get("region_count", len(regions)) or 0)
    edge_density = float(primary.get("edge_density", 0.0) or 0.0)

    header_region = _largest_region_for_roles(regions, {"header"})
    sidebar_region = _largest_region_for_roles(regions, {"sidebar"})
    content_region = _largest_region_for_roles(regions, {"content", "panel"})
    input_region = _largest_region_for_roles(regions, {"input", "footer"})

    header_box = _normalized_box(
        header_region,
        defaults=(0, 0, window_w, max(52, int(window_h * 0.12))),
        window_w=window_w,
        window_h=window_h,
        min_w=220,
        min_h=44,
    )
    sidebar_box = _normalized_box(
        sidebar_region,
        defaults=(int(window_w * 0.02), int(window_h * 0.16), int(window_w * 0.22), int(window_h * 0.70)),
        window_w=window_w,
        window_h=window_h,
        min_w=110,
        min_h=120,
    )
    content_box = _normalized_box(
        content_region,
        defaults=(int(window_w * 0.27), int(window_h * 0.18), int(window_w * 0.70), int(window_h * 0.58)),
        window_w=window_w,
        window_h=window_h,
        min_w=220,
        min_h=140,
    )
    input_box = _normalized_box(
        input_region,
        defaults=(int(window_w * 0.27), int(window_h * 0.80), int(window_w * 0.48), int(window_h * 0.08)),
        window_w=window_w,
        window_h=window_h,
        min_w=180,
        min_h=36,
    )

    action_default = {
        "x": int(window_w * 0.77),
        "y": int(window_h * 0.80),
        "width": int(window_w * 0.18),
        "height": int(window_h * 0.08),
    }

    button_regions = []
    for region in regions:
        if not isinstance(region, dict):
            continue
        if region.get("role") not in {"button", "icon", "toolbar_item"}:
            continue
        button_regions.append(region)
    if not button_regions:
        button_regions.append(action_default)

    button_regions = button_regions[:MAX_TEMPLATE_ACTION_BUTTONS]
    button_boxes = []
    for index, button_region in enumerate(button_regions, start=1):
        fallback_x = action_default["x"]
        fallback_y = action_default["y"] - (index - 1) * clamp_int(int(window_h * 0.11), 34, 90)
        fallback_w = action_default["width"]
        fallback_h = action_default["height"]
        button_boxes.append(
            _normalized_box(
                button_region,
                defaults=(fallback_x, fallback_y, fallback_w, fallback_h),
                window_w=window_w,
                window_h=window_h,
                min_w=72,
                min_h=30,
            )
        )

    template_image_path = str(primary.get("path", "")).strip()
    if not template_image_path and template_png_paths:
        template_image_path = str(template_png_paths[0])
    has_template_image = bool(template_image_path)
    template_image_b64 = _load_template_image_base64(template_image_path) if has_template_image else ""
    if form_items:
        # Keep form list readable even when the uploaded template is dark/noisy.
        template_image_path = ""
        template_image_b64 = ""
        has_template_image = False

    if explicit_header_text:
        window_title = explicit_header_text
    else:
        window_title = _preferred_window_title(output_text, "")

    app_id_stem = re.sub(r"[^a-z0-9]+", "", output_file.stem.lower())
    if not app_id_stem:
        app_id_stem = "generated"
    app_id = f"com.texteditor.{app_id_stem}"

    use_visual_match_mode = (
        has_template_image
        or
        region_count <= 2
        or edge_density <= 0.028
        or (header_region is None and sidebar_region is None and content_region is None and input_region is None)
    )
    if use_visual_match_mode and not form_items:
        background_hex = _template_background_hex(primary)
        overlay_text = ""
        overlay_alignment = "start"
        if not has_template_image:
            overlay_text = header_text
            if _detect_center_text_region(regions, window_w, window_h):
                overlay_alignment = "center"
        return _build_visual_match_code(
            window_title=window_title,
            overlay_text=overlay_text,
            overlay_alignment=overlay_alignment,
            app_id=app_id,
            window_w=window_w,
            window_h=window_h,
            background_hex=background_hex,
            template_image_path=template_image_path,
            template_image_b64=template_image_b64,
            is_resizable=resize_requested,
        )

    hx, hy, hw, hh = header_box
    sx, sy, sw, sh = sidebar_box
    cx, cy, cw, ch = content_box
    ix, iy, iw, ih = input_box
    header_text_y = hy + max(8, int(hh * 0.25))
    header_text_x = hx + max(14, int(hw * 0.04))

    lines = [
        "import os",
        "import sys",
        "",
        "import gi",
        'gi.require_version("Gtk", "3.0")',
        "from gi.repository import Gtk",
        "",
        f"TEMPLATE_IMAGE = {json.dumps(template_image_path)}",
        "",
        "class TemplateGeneratedWindow(Gtk.ApplicationWindow):",
        "    def __init__(self, app):",
        f"        super().__init__(application=app, title={json.dumps(window_title)})",
        f"        self.set_default_size({window_w}, {window_h})",
        "        self.set_position(Gtk.WindowPosition.CENTER)",
    ]
    if resize_requested:
        lines.append("        self.set_resizable(True)")

    lines.extend(
        [
            "",
            "        overlay = Gtk.Overlay()",
            "        self.add(overlay)",
            "",
            "        if TEMPLATE_IMAGE and os.path.isfile(TEMPLATE_IMAGE):",
        "            background = Gtk.Image.new_from_file(TEMPLATE_IMAGE)",
        "            background.set_hexpand(True)",
        "            background.set_vexpand(True)",
        "            overlay.add(background)",
        "        else:",
        "            overlay.add(Gtk.Box(orientation=Gtk.Orientation.VERTICAL))",
        "",
        "        fixed = Gtk.Fixed()",
        "        fixed.set_hexpand(True)",
        "        fixed.set_vexpand(True)",
        "        overlay.add_overlay(fixed)",
        "",
        "        header_panel = Gtk.Frame()",
        f"        header_panel.set_size_request({hw}, {hh})",
        f"        fixed.put(header_panel, {hx}, {hy})",
        "",
        f"        header_label = Gtk.Label(label={json.dumps(header_text)})",
        "        header_label.set_xalign(0.0)",
        f"        fixed.put(header_label, {header_text_x}, {header_text_y})",
        "",
        "        sidebar = Gtk.Frame(label='Navigation')",
        f"        sidebar.set_size_request({sw}, {sh})",
        f"        fixed.put(sidebar, {sx}, {sy})",
        "",
        "        output_scroller = Gtk.ScrolledWindow()",
        "        output_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)",
        f"        output_scroller.set_size_request({cw}, {ch})",
        "",
        "        entry = Gtk.Entry()",
        "        entry.set_placeholder_text('Type here')",
        f"        entry.set_size_request({iw}, {ih})",
        f"        fixed.put(entry, {ix}, {iy})",
        "",
        ]
    )

    if form_items:
        lines.extend(
            [
                "        # @form items injected by texteditor agent",
                f"        form_list = Gtk.ListBox()",
                "        form_list.set_selection_mode(Gtk.SelectionMode.SINGLE)",
                f"        for form_item in {json.dumps(form_items)}:",
                "            row = Gtk.ListBoxRow()",
                "            row_label = Gtk.Label(label=form_item, xalign=0.0)",
                "            row_label.set_margin_top(6)",
                "            row_label.set_margin_bottom(6)",
                "            row_label.set_margin_start(8)",
                "            row_label.set_margin_end(8)",
                "            row.add(row_label)",
                "            form_list.add(row)",
                "        output_scroller.add(form_list)",
                f"        fixed.put(output_scroller, {cx}, {cy})",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "        output_view = Gtk.TextView()",
                "        output_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)",
                "        output_view.set_editable(False)",
                "        output_view.set_cursor_visible(False)",
                f"        output_view.get_buffer().set_text({json.dumps(output_text)})",
                "        output_scroller.add(output_view)",
                f"        fixed.put(output_scroller, {cx}, {cy})",
                "",
            ]
        )

    for index, (bx, by, bw, bh) in enumerate(button_boxes, start=1):
        lines.extend(
            [
                f"        action_button_{index} = Gtk.Button(label='Action {index}')",
                f"        action_button_{index}.set_size_request({bw}, {bh})",
                f"        fixed.put(action_button_{index}, {bx}, {by})",
                "",
            ]
        )

    lines.extend(
        [
            "",
            "class TemplateGeneratedApp(Gtk.Application):",
            "    def __init__(self):",
            f"        super().__init__(application_id={json.dumps(app_id)})",
            "",
            "    def do_activate(self):",
            "        window = self.props.active_window",
            "        if not window:",
            "            window = TemplateGeneratedWindow(self)",
            "        window.present()",
            "",
            "if __name__ == '__main__':",
            "    app = TemplateGeneratedApp()",
            "    app.run(sys.argv)",
        ]
    )

    return "\n".join(lines)


def main():
    configure_console_output_encoding()
    model_name = load_selected_model()
    react_max_steps = load_react_max_steps()
    active_file_path = os.getenv("TEXTEDITOR_ACTIVE_FILE", "")
    source_file = resolve_source_file(active_file_path)
    output_file = choose_output_file(source_file).resolve()
    resize_requested = source_requests_resizable_window(source_file)
    form_items = extract_form_items_from_source(source_file)

    (
        template_context,
        template_png_count,
        original_template_analysis,
        processed_template_analysis,
        _template_dir,
        template_png_paths,
    ) = build_template_context(source_file)

    primary_template_analysis = original_template_analysis or processed_template_analysis
    selected_template = pick_primary_template_entry(
        template_analysis=primary_template_analysis,
        template_png_paths=template_png_paths,
        source_file=source_file,
    )

    project_dir = source_file.parent.resolve()
    project_context = build_project_context(project_dir, source_file)
    task = build_generation_task(
        source_file=source_file,
        output_file=output_file,
        project_context=project_context,
        template_context=template_context,
        template_png_count=template_png_count,
        form_items=form_items,
    )

    agent = build_reasoning_agent(model_name, tools=select_agent_tools(template_png_count))
    try:
        result = agent.run(task=task, max_steps=react_max_steps)
        generated_code = extract_python_code(coerce_agent_output_text(result))
    except Exception as exc:
        if template_png_count > 0:
            generation_mode = "react_exception_fallback_template_synthesis"
            if is_context_length_error(exc):
                generation_mode = "react_context_fallback_template_synthesis"
            print(f"Agent reasoning exception: {type(exc).__name__}: {exc}")
            generated_code = build_template_driven_code(
                source_file=source_file,
                output_file=output_file,
                template_analysis=original_template_analysis or processed_template_analysis,
                template_png_paths=template_png_paths,
                form_items=form_items,
            )
            generated_code = apply_resize_directive_to_generated_code(
                generated_code=generated_code,
                should_resize=resize_requested,
            )
            generated_code = apply_form_directive_to_generated_code(
                generated_code=generated_code,
                form_items=form_items,
            )
            output_file, backup_file = write_generated_code(output_file, generated_code)
            print(f"Source file: {source_file}")
            print(f"Template directory: {resolve_templates_directory(source_file)}")
            print(f"Template image: {selected_template.get('path', '')}")
            print(f"Generation mode: {generation_mode}")
            print(f"Generated file: {output_file}")
            if backup_file is not None:
                print(f"Backup saved: {backup_file}")
            return
        raise

    generation_mode = "react_code_agent"
    if should_fallback_to_template_synthesis(
        generated_code=generated_code,
        template_png_count=template_png_count,
        selected_template=selected_template,
    ):
        generation_mode = "react_code_agent_fallback_template_synthesis"
        generated_code = build_template_driven_code(
            source_file=source_file,
            output_file=output_file,
            template_analysis=original_template_analysis or processed_template_analysis,
            template_png_paths=template_png_paths,
            form_items=form_items,
        )

    generated_code = apply_resize_directive_to_generated_code(
        generated_code=generated_code,
        should_resize=resize_requested,
    )
    generated_code = apply_form_directive_to_generated_code(
        generated_code=generated_code,
        form_items=form_items,
    )

    output_file, backup_file = write_generated_code(output_file, generated_code)

    print(f"Source file: {source_file}")
    print(f"Template directory: {resolve_templates_directory(source_file)}")
    print(f"Template image: {selected_template.get('path', '')}")
    print(f"Generation mode: {generation_mode}")
    print(f"Generated file: {output_file}")
    if backup_file is not None:
        print(f"Backup saved: {backup_file}")


if __name__ == "__main__":
    main()
