import os
from dotenv import load_dotenv
from groq import Groq
from groq.types.chat import ChatCompletionMessageParam
import base64
import copy

class ConversationAgent:
    def __init__(self):
        load_dotenv()
        self.client = Groq(api_key=os.environ["GROQ_KEY"])
        self.initiate_history()

    @staticmethod
    def read_file(file_path):
        with open(file_path, "r") as file:
            return file.read()
        
    @staticmethod
    def read_image(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def initiate_history(self):
        self.history: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": self.read_file(os.path.dirname(__file__) + '/../ressources/teacher_context.txt')
            }
        ]

    def update_history(self, role, content):
         self.history.append(
            {
                "role": role,
                "content": content,
            })
    
    def get_history(self):
        return self.history
    
    def get_cleaned_api_history(self, include_multimodal_content=False, current_multimodal_content=None):
        messages_to_send = copy.deepcopy(self.history)
        
        for i, message in enumerate(messages_to_send):
            
            if "image_url" in message:
                del message["image_url"]

            if isinstance(message.get("content"), list):
                try:
                    text_content = next(item['text'] for item in message['content'] if item['type'] == 'text')
                    message['content'] = text_content
                except (StopIteration, KeyError):
                    message['content'] = ""

        if include_multimodal_content and current_multimodal_content is not None:
            
            if messages_to_send[-1]["role"] == "user":
                messages_to_send[-1]["content"] = current_multimodal_content
            else:
                pass

        return messages_to_send
    
    def ask_llm(self, user_interaction, model):

        self.update_history(role="user", content=user_interaction)
        
        cleaned_messages = self.get_cleaned_api_history(
            include_multimodal_content=False
        )

        response = self.client.chat.completions.create(
            messages=cleaned_messages,
            model=model
        )
        
        assistant_content = response.choices[0].message.content
        self.update_history(role="assistant", content=assistant_content)

        return response
    
    def ask_vision_model(self, user_interaction, image_b64, mime_type, image_url_for_display):

        multimodal_content_api = [
            {"type": "text", "text": user_interaction},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{image_b64}",
                },
            },
        ]

        self.update_history(
            role="user", 
            content=user_interaction,
            image_url=image_url_for_display
        )
        
        messages_to_send = self.get_cleaned_api_history(
            include_multimodal_content=True,
            current_multimodal_content=multimodal_content_api
        )

        response = self.client.chat.completions.create(
            messages=messages_to_send,
            model="meta-llama/llama-4-scout-17b-16e-instruct",
        ).choices[0].message.content

        self.update_history(role="assistant", content=response)

        return response