from groq import Groq
from dotenv import load_dotenv
import os

class ConversationAgent:
    def __init__(self):
        load_dotenv()
        self.client = Groq(api_key=os.environ["GROQ_KEY"])
        
        
