import os
from google import genai
from google.genai.types import HttpOptions

def check(model_id, version):
    try:
        client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'), http_options=HttpOptions(api_version=version))
        m = client.models.get(model=model_id)
        # In version 1.0.0+, m.supported_methods is a list of strings
        methods = getattr(m, 'supported_methods', [])
        is_bidi = 'bidiGenerateContent' in methods
        print(f"{model_id} ({version}): {'✅ BIDI SUPPORTED' if is_bidi else '❌ No bidi'} | Methods: {methods}")
    except Exception as e:
        print(f"{model_id} ({version}): ⚠️ Error: {e}")

if __name__ == "__main__":
    for ver in ['v1beta', 'v1alpha']:
        for m in ['gemini-2.0-flash', 'gemini-2.0-flash-exp', 'gemini-1.5-flash']:
            check(m, ver)
            check(f"models/{m}", ver)
