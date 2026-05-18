"""Simple Perplexity API test to find correct model name"""

import os

from dotenv import load_dotenv

load_dotenv()

from perplexity import Perplexity

# Test with different model names
models_to_test = [
    "sonar",
    "sonar-small-chat",
    "sonar-medium-chat",
    "llama-3.1-sonar-small-128k-online",
    "llama-3.1-sonar-large-128k-online",
]

api_key = os.getenv("PERPLEXITY_API_KEY")
print(f"API Key: {api_key[:15]}...")

client = Perplexity(api_key=api_key)

for model in models_to_test:
    try:
        print(f"\nTesting model: {model}")
        response = client.chat.completions.create(model=model, messages=[{"role": "user", "content": "What is 2+2?"}])
        print(f"✅ SUCCESS with model: {model}")
        print(f"Response: {response.choices[0].message.content[:100]}")
        break
    except Exception as e:
        print(f"❌ Failed: {str(e)[:100]}")
