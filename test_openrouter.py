from llm import get_llm_output

print("🧪 Testing OpenRouter API...\n")

# Test simple query
response = get_llm_output("Hello, what's the weather like today?")

print(f"✅ Response received:")
print(f"   Intent: {response['intent']}")
print(f"   Text: {response['text']}")
print(f"   Needs Clarification: {response['needs_clarification']}")
print(f"   Parameters: {response['parameters']}")

if response['text'] and response['text'] != "OpenRouter API key is missing, Sir.":
    print("\n✅ OpenRouter API is working correctly!")
else:
    print("\n❌ OpenRouter API test failed!")
