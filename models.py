import os

import dotenv
from google import genai

dotenv.load_dotenv()

client = genai.Client(
    api_key=os.getenv("GOOGLE_API_KEY"),
)

print("List of models that support generateContent:\n")
for m in client.models.list():
    for action in m.supported_actions:
        if action == "generateContent":
            print(m.name)

print("List of models that support embedContent:\n")
for m in client.models.list():
    for action in m.supported_actions:
        if action == "embedContent":
            print(m.name)
