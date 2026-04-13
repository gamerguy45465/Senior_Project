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
DEFAULT_SMOLAGENTS_FALLBACK_MODEL = "gpt-4o-mini"
MAX_TEMPLATE_IMAGES_FOR_PROMPT = 8
MAX_TEMPLATE_ANALYSIS_CHARS = 8_000
REACT_PLANNING_INTERVAL = 1
REACT_MAX_STEPS = 4
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


def resolve_smolagents_model(model_name):
    selected = (model_name or "").strip()
    fallback = os.getenv("TEXTEDITOR_SMOLAGENTS_FALLBACK_MODEL", DEFAULT_SMOLAGENTS_FALLBACK_MODEL).strip()
    fallback = fallback or DEFAULT_SMOLAGENTS_FALLBACK_MODEL
    normalized = selected.lower()

    if any(normalized.startswith(prefix) for prefix in RESPONSES_ONLY_MODEL_PREFIXES):
        return fallback, (
            f"Selected model '{selected}' is Responses-only. "
            f"Using chat-compatible fallback '{fallback}' for SmolAgents tool-calling."
        )

    return selected, None


def build_reasoning_agent(model_name, tools=None):
    api_key = load_api_key()
    resolved_model, warning = resolve_smolagents_model(model_name)
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
        planning_interval=REACT_PLANNING_INTERVAL,
        max_steps=REACT_MAX_STEPS,
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


def build_generation_task(source_file, output_file, project_context, template_context, template_png_count):
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
            "Output GTK code that mirrors the original template image dimensions and composition."
        )
    else:
        template_hint = (
            "Template requirement: no template PNGs were found in the available Templates directories. "
            "Fallback to source code context for layout decisions."
        )

    return (
        f"Task: Generate a GTK GUI for {source_file.name}.\n"
        f"Write the result as a standalone Python module for a new file named {output_file.name}.\n"
        "Requirement: if there is a decorator @output \"Hello World\", remove that "
        "decorator usage and render the same text in a GTK text widget.\n"
        f"{template_hint}\n"
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


def is_context_length_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "context_length_exceeded" in text or "maximum context length" in text


def extract_output_text_from_source(source_file):
    try:
        content = source_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "Generated Interface"

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


def _build_visual_match_code(output_text, app_id, window_w, window_h, background_hex):
    return "\n".join(
        [
            "import sys",
            "",
            "import gi",
            'gi.require_version("Gtk", "3.0")',
            "from gi.repository import Gdk, Gtk",
            "",
            f"WINDOW_BG = {json.dumps(background_hex)}",
            "",
            "class TemplateGeneratedWindow(Gtk.ApplicationWindow):",
            "    def __init__(self, app):",
            f"        super().__init__(application=app, title={json.dumps(output_text)})",
            f"        self.set_default_size({window_w}, {window_h})",
            "        self.set_position(Gtk.WindowPosition.CENTER)",
            "        self.set_resizable(False)",
            "",
            "        body = Gtk.EventBox()",
            "        body.set_name('template_body')",
            "        body.set_hexpand(True)",
            "        body.set_vexpand(True)",
            "        self.add(body)",
            "",
            "        css = Gtk.CssProvider()",
            "        css.load_from_data((",
            "            '#template_body {'",
            "            '  background-color: ' + WINDOW_BG + ';'",
            "            '}'",
            "        ).encode('utf-8'))",
            "        screen = Gdk.Screen.get_default()",
            "        if screen is not None:",
            "            Gtk.StyleContext.add_provider_for_screen(",
            "                screen,",
            "                css,",
            "                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,",
            "            )",
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


def build_template_driven_code(source_file, output_file, template_analysis, template_png_paths):
    primary = pick_primary_template_entry(
        template_analysis=template_analysis,
        template_png_paths=template_png_paths,
        source_file=source_file,
    )
    output_text = extract_output_text_from_source(source_file)

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

    app_id_stem = re.sub(r"[^a-z0-9]+", "", output_file.stem.lower())
    if not app_id_stem:
        app_id_stem = "generated"
    app_id = f"com.texteditor.{app_id_stem}"

    use_visual_match_mode = (
        region_count <= 2
        or edge_density <= 0.028
        or (header_region is None and sidebar_region is None and content_region is None and input_region is None)
    )
    if use_visual_match_mode:
        background_hex = _template_background_hex(primary)
        return _build_visual_match_code(
            output_text=output_text,
            app_id=app_id,
            window_w=window_w,
            window_h=window_h,
            background_hex=background_hex,
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
        f"        super().__init__(application=app, title={json.dumps(output_text)})",
        f"        self.set_default_size({window_w}, {window_h})",
        "        self.set_position(Gtk.WindowPosition.CENTER)",
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
        f"        header_label = Gtk.Label(label={json.dumps(output_text)})",
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
        "        output_view = Gtk.TextView()",
        "        output_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)",
        "        output_view.set_editable(False)",
        "        output_view.set_cursor_visible(False)",
        f"        output_view.get_buffer().set_text({json.dumps(output_text)})",
        "        output_scroller.add(output_view)",
        f"        fixed.put(output_scroller, {cx}, {cy})",
        "",
        "        entry = Gtk.Entry()",
        "        entry.set_placeholder_text('Type here')",
        f"        entry.set_size_request({iw}, {ih})",
        f"        fixed.put(entry, {ix}, {iy})",
        "",
    ]

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
    model_name = load_selected_model()
    active_file_path = os.getenv("TEXTEDITOR_ACTIVE_FILE", "")
    source_file = resolve_source_file(active_file_path)
    output_file = choose_output_file(source_file).resolve()

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
    )

    agent = build_reasoning_agent(model_name, tools=select_agent_tools(template_png_count))
    try:
        result = agent.run(task=task, max_steps=REACT_MAX_STEPS)
        generated_code = extract_python_code(coerce_agent_output_text(result))
    except Exception as exc:
        if template_png_count > 0 and is_context_length_error(exc):
            generation_mode = "react_context_fallback_template_synthesis"
            generated_code = build_template_driven_code(
                source_file=source_file,
                output_file=output_file,
                template_analysis=processed_template_analysis or original_template_analysis,
                template_png_paths=template_png_paths,
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
    if template_png_count > 0 and not looks_like_gtk_code(generated_code):
        generation_mode = "react_code_agent_fallback_template_synthesis"
        generated_code = build_template_driven_code(
            source_file=source_file,
            output_file=output_file,
            template_analysis=processed_template_analysis or original_template_analysis,
            template_png_paths=template_png_paths,
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
