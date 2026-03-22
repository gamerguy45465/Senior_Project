from openai import OpenAI
import os
from dotenv import load_dotenv
from smolagents import ToolCallingAgent

current_model = "gpt-5.2" # I will eventually make this so that it can be set. For now, it will be hard coded.











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