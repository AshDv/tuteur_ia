import os
from dotenv import load_dotenv
from groq import Groq
from groq.types.chat import ChatCompletionMessageParam
from quiz_agent import QuizAgent
import base64
import copy
import json

class ConversationAgent:
    def __init__(self, quiz_agent: QuizAgent):
        load_dotenv()
        self.client = Groq(api_key=os.environ["GROQ_KEY"])
        self.initiate_history()
        self.quiz_agent = quiz_agent

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
    
    def generate_quiz(self, topic, n_questions=5, model="llama3-70b-8192"):
        
        prompt_quiz = f"""
        Génère un quiz de {n_questions} questions sur le sujet '{topic}'. 
        Le quiz doit être un mélange des deux types : 'open' (réponse rédigée) et 'qcm' (question à choix multiples).

        Le format de sortie DOIT être un tableau JSON (liste Python) sans aucun texte explicatif avant ou après. Chaque objet du tableau doit avoir les clés suivantes :
        1. "type": ('open' ou 'qcm').
        2. "question": (string).
        3. "explanation": (string, explication pédagogique complète pour la correction).
        4. "correct_identifier": (string. Pour 'open', c'est la réponse détaillée attendue. Pour 'qcm', c'est la lettre correcte, ex: 'B').

        SI le type est 'qcm', ajoute la clé supplémentaire :
        5. "choices": (array de 4 strings pour les options A, B, C, D).
        """
        
        quiz_context = self.read_file(os.path.dirname(__file__) + '/../ressources/quiz_context.txt')
        messages_to_send = [
            {
                "role": "system", 
                "content": quiz_context
            },
            {"role": "user", "content": prompt_quiz}
        ]
        
        try:
            raw_response = self.client.chat.completions.create(
                messages=messages_to_send,
                model=model, 
            ).choices[0].message.content

            if raw_response.strip().startswith("```json"):
                raw_response = raw_response.strip().strip("```json").strip("```").strip()

            quiz_data = json.loads(raw_response)
            
            self.quiz_agent.create_quiz(quiz_data) 
            
            return True
            
        except json.JSONDecodeError as e:
            print(f"Erreur de décodage JSON. Réponse brute: {raw_response[:200]}")
            return False 
        except Exception as e:
            print(f"Erreur lors de l'appel à l'API Groq : {e}")
            return False
        
    def evaluate_and_get_feedback(self, question_data: dict, user_answer: str, model="llama3-70b-8192"):
    
        q_type = question_data['type']
        correct_identifier = question_data['correct_identifier']
        explanation = question_data['explanation']
        
        if q_type == 'qcm':
            score = 1 if user_answer.strip().upper() == correct_identifier.strip().upper() else 0
            
            if score == 1:
                feedback = "⭐ Félicitations, jeune disciple. Votre choix est exact. La connaissance est une arme bien aiguisée !"
            else:
                feedback = f"❌ Réponse incorrecte. La patience est la clé, mon jeune élève. Méditez sur votre erreur. Voici l'explication : {explanation}"
                
            return {"score": score, "feedback": feedback}

        
        else:
            
            teacher_context = self.read_file(os.path.dirname(__file__) + '/../ressources/teacher_context.txt')
            
            prompt_correction = f"""
            TACHE : En tant que Maître Splinter, évalue la réponse de l'étudiant.
            Réponse attendue (Référence pour la notation) : '{correct_identifier}'
            Réponse de l'étudiant : '{user_answer}'
            
            [Explication détaillée fournie si besoin : {explanation}]
            
            RÈGLE DE NOTATION :
            1. Décide si la réponse est CORRECTE (score 1) ou INCORRECTE (score 0).
            2. Le 'feedback' doit être formulé avec le ton sage et pédagogique de Maître Splinter.
            
            FORMAT DE SORTIE OBLIGATOIRE :
            Retourne UNIQUEMENT l'objet JSON suivant sans aucun texte supplémentaire :
            {{"score": (int), "feedback": (string formulé par Maître Splinter)}}
            """

            messages_to_send = [
                {"role": "system", "content": teacher_context},
                {"role": "user", "content": prompt_correction} 
            ]

            try:
                raw_response = self.client.chat.completions.create(
                    messages=messages_to_send,
                    model=model,
                ).choices[0].message.content
                
                if raw_response.strip().startswith("```json"):
                    raw_response = raw_response.strip().strip("```json").strip("```").strip()

                return json.loads(raw_response)
            
            except json.JSONDecodeError:
                return {f"Erreur de décodage JSON. Réponse brute: {raw_response[:200]}"}
            except Exception as e:
                return {f"Erreur lors de l'appel à l'API Groq : {e}"}