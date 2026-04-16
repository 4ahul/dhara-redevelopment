import anthropic

client = anthropic.Anthropic(
    api_key="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"
)

try:
    res = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=20,
        messages=[{"role": "user", "content": "Hi"}],
    )
    print("✅ Working:", res.content[0].text)

except Exception as e:
    print("❌ Error:", e)
