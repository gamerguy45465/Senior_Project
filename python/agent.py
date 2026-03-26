from openai import OpenAI
import json
import os
import sys
from dotenv import load_dotenv
from smolagents import ToolCallingAgent

DEFAULT_MODEL = "gpt-5.2"


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

    # Fallback for local development so settings still work when no config root exists.
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


current_model = load_selected_model()











def build_reasoning_model(): # Used to build the client object the application will be interacting with
    key_name = "OPENAI_API_KEY"
    load_dotenv()
    api_key = os.getenv(key_name)

    if not api_key:
        message = (f"Error: {key_name} is not set."
                   f"Please ensure that you have a proper API key from OpenAI."
                   f"For more information, please go to: "
                   f"https://openai.com/api/")

        raise ValueError(message)

    client = OpenAI(api_key=api_key)

    return client




def main():
    client = build_reasoning_model()




    response = client.responses.create(
        model=current_model, # Set the model to the current model, which can be changed in the settings
        reasoning={"effort": "high"},
        input=[
            {
                "role": "system",
                "content": "You will eventually be an agent for reading a python script, and then generating a GUI for that python script. Right now you are in the process of telling me what you can do. For example, can you use a given python script, and generate a GUI with GTK using information from that script. What information will you need for such a task?"
            },
            {
                "role": "user",
                "content": "What do you need for generating a GUI for a python program using GTK?"

            }

        ]
    )



    print(response.output_text)















if __name__ == '__main__':
    main()
