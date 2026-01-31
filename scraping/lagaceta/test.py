import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Resumí esta noticia: Un grupo de orcas fue visto usando algas para frotarse la piel..."}]
)

print(response.choices[0].message.content)