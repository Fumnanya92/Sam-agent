from llm import get_llm_output
import json

print("🧪 Testing OpenAI API with detailed debug...\n")

# Test simple query
response = get_llm_output("Hello Sam, what time is it?")

print(f"✅ Full response:")
print(json.dumps(response, indent=2))

if response['text'] and "API error" not in response['text']:
    print("\n✅ OpenAI API is working correctly!")
else:
    print("\n❌ OpenAI API test failed!")