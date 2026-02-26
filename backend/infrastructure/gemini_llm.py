import os
import google.generativeai as genai
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=env_path)

# Configure strictly for drafting texts, not logic decisions
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "dummy_key"))

class GeminiDraftingClient:
    @staticmethod
    def generate_draft(prompt: str) -> str:
        """
        Calls Gemini strictly to generate draft text. 
        Does not ask LLM for entity tracking or routing decisions.
        """
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error generating draft: {str(e)}"
