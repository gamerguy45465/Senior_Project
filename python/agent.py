from openai import OpenAI
import os
from dotenv import load_dotenv















def main():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")

    print(api_key)

    client = OpenAI()




    response = client.responses.create(
        model="gpt-5.2",
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




    #print(response.choices[0].message.contents)



    print(response.output_text)















if __name__ == '__main__':
    main()