import json
import os
import subprocess
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    from openai import OpenAI
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openai"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dotenv"])
    from dotenv import load_dotenv
    from openai import OpenAI


DEFAULT_MODEL = "gpt-5-codex"
REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_FILE_BYTES = 100_000
MAX_TOTAL_CONTEXT_CHARS = 120_000


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


def build_reasoning_model():
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

    return OpenAI(api_key=api_key)


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


def build_project_context(project_dir, source_file):
    sections = [f"Project root: {project_dir}", f"Primary file: {source_file.name}"]
    total_chars = len(sections[0]) + len(sections[1]) + 2
    files_added = 0
    files_skipped = 0

    file_candidates = [source_file]
    file_candidates.extend(sorted(project_dir.rglob("*")))
    seen_files = set()

    for file_path in file_candidates:
        try:
            resolved_file = file_path.resolve()
        except OSError:
            files_skipped += 1
            continue

        if resolved_file in seen_files:
            continue
        seen_files.add(resolved_file)

        if not resolved_file.is_file():
            continue

        try:
            file_size = resolved_file.stat().st_size
        except OSError:
            files_skipped += 1
            continue

        if file_size > MAX_FILE_BYTES:
            files_skipped += 1
            continue

        try:
            content = resolved_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            files_skipped += 1
            continue

        try:
            relative_name = resolved_file.relative_to(project_dir).as_posix()
        except ValueError:
            files_skipped += 1
            continue
        file_block = f"\n\n### {relative_name}\n```text\n{content}\n```"

        if total_chars + len(file_block) > MAX_TOTAL_CONTEXT_CHARS:
            files_skipped += 1
            continue

        sections.append(file_block)
        total_chars += len(file_block)
        files_added += 1

    sections.append(
        f"\n\nContext summary: included={files_added}, skipped={files_skipped}, "
        f"max_file_bytes={MAX_FILE_BYTES}, max_total_chars={MAX_TOTAL_CONTEXT_CHARS}."
    )
    return "".join(sections)


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


def main():
    client = build_reasoning_model()
    model_name = load_selected_model()

    active_file_path = os.getenv("TEXTEDITOR_ACTIVE_FILE", "")
    source_file = resolve_source_file(active_file_path)
    project_dir = source_file.parent.resolve()
    project_context = build_project_context(project_dir, source_file)
    output_file = choose_output_file(source_file).resolve()

    response = client.responses.create(
        model=model_name,
        reasoning={"effort": "high"},
        input=[
            {
                "role": "system",
                "content": (
                    "You are a Python assistant. You cannot directly browse the local filesystem, "
                    "so use only the project files provided in the user message."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Task: Generate a GTK GUI for {source_file.name} using the project context below.\n"
                    f"Write the result as a standalone Python module for a new file named {output_file.name}.\n"
                    "Requirement: if there is a decorator @output \"Hello World\", remove that "
                    "decorator usage and render the same text in a GTK text widget.\n"
                    "Return only the resulting Python code.\n\n"
                    f"{project_context}"
                ),
            },
        ],
    )

    generated_code = extract_python_code(response.output_text)
    output_file, backup_file = write_generated_code(output_file, generated_code)

    print(f"Source file: {source_file}")
    print(f"Generated file: {output_file}")
    if backup_file is not None:
        print(f"Backup saved: {backup_file}")


if __name__ == "__main__":
    main()
