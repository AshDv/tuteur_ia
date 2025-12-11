import requests
import os
import json
import copy
import streamlit as streamlit
from groq import Groq
from dotenv import load_dotenv
from groq.types.chat import ChatCompletionMessageParam
from quiz_agent import QuizAgent

load_dotenv()
class ConversationAgent:
    
    TEACHER_CONTEXT_PATH = os.path.join(os.path.dirname(__file__) + '/../resources/teacher_context.txt')
    QUIZ_CONTEXT_PATH = os.path.join(os.path.dirname(__file__) + '/../resources/teacher_context.txt')

    def __init__(self, quiz_agent: QuizAgent):
        api_key = os.environ.get("GROQ_KEY")
        if not api_key:
            raise ValueError("GROQ_KEY non trouvée dans les variables d'environnement.")
            
        self.client = Groq(api_key=api_key)
        self.quiz_agent = quiz_agent # Injection de dépendance
        
        self.initiate_history()

    @streamlit.cache_data(ttl=3600)
    def fetch_groq_models():
        """Récupère la liste dynamique des modèles disponibles sur Groq."""
        
        api_key = os.environ.get("GROQ_KEY")
        if not api_key:
            return []

        url = "https://api.groq.com/openai/v1/models"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10) # Timeout pour la sécurité
            response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP
            
            data = response.json()
            
            # Filtre et formatage pour Streamlit
            model_names = [model['id'] for model in data['data'] if model['id'].startswith(('llama', 'mixtral'))]
            return model_names
            
        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la récupération des modèles Groq: {e}")
            # Modèles par défaut en cas d'échec de l'API
            return ["llama3-70b-8192", "mixtral-8x7b-8192"]

    @staticmethod
    def read_file(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()

    def initiate_history(self):
        try:
            system_content = self.read_file(self.TEACHER_CONTEXT_PATH)
        except FileNotFoundError:
            system_content = "Vous êtes un tuteur IA, sage et pédagogue."
            
        self.history: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": system_content
            }
        ]

    # --- Gestion de l'Historique ---

    def update_history(self, role, content, image_url=None):
        """Ajoute un message à l'historique persistant (pour l'affichage)."""
        message_data = {"role": role, "content": content}
        
        if image_url:
            message_data["image_url"] = image_url 
            
        self.history.append(message_data)
        
    def get_history(self):
        """Retourne l'historique complet (pour l'affichage)."""
        return self.history

    def get_cleaned_api_history(self, include_multimodal_content=False, current_multimodal_content=None):
        """
        Retourne une copie de l'historique nettoyée pour les appels d'API Groq:
        1. Supprime la clé 'image_url'.
        2. Simplifie les anciens messages multimodaux en texte pur.
        3. Injecte le contenu multimodal pour le message actuel si demandé.
        """
        messages_to_send = copy.deepcopy(self.history)
        
        for message in messages_to_send:
            
            # 1. Suppression de la clé d'affichage non standard Groq
            if "image_url" in message:
                del message["image_url"]

            # 2. Simplification des anciens messages multimodaux (si le 'content' est une liste)
            if isinstance(message.get("content"), list):
                try:
                    # Extrait seulement la partie textuelle du contenu multimodal
                    text_content = next(item['text'] for item in message['content'] if item['type'] == 'text')
                    message['content'] = text_content
                except (StopIteration, KeyError):
                    message['content'] = ""

        # 3. Injection du contenu multimodal actuel (uniquement pour l'agent vision)
        if include_multimodal_content and current_multimodal_content is not None:
            if messages_to_send[-1]["role"] == "user":
                messages_to_send[-1]["content"] = current_multimodal_content
        
        return messages_to_send

    # --- Logique d'Exécution ---

    def ask_llm(self, user_interaction, model, context_text=""):
        teacher_context = self.read_file(self.TEACHER_CONTEXT_PATH)
        system_content = f"{teacher_context}\n\n[CONTEXTE DE COURS]: {context_text}" if context_text else teacher_context
        
        self.update_history(role="user", content=user_interaction)
        
        cleaned_messages = self.get_cleaned_api_history(include_multimodal_content=False)
        
        cleaned_messages[0] = {"role": "system", "content": system_content}

        try:
            response = self.client.chat.completions.create(
                messages=cleaned_messages,
                model=model
            )
            assistant_content = response.choices[0].message.content
            
            self.update_history(role="assistant", content=assistant_content)
            return assistant_content
        
        except Exception as e:
            error_msg = f"❌ Maître Splinter : Une erreur API est survenue pendant la conversation : {e}"
            self.update_history(role="assistant", content=error_msg)
            return error_msg

    def ask_vision_model(self, user_interaction, image_b64, mime_type, image_url_for_display, model):

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
        
        try:
            response = self.client.chat.completions.create(
                messages=messages_to_send,
                model=model,
            ).choices[0].message.content
            
            self.update_history(role="assistant", content=response)
            return response
        
        except Exception as e:
            error_msg = f"❌ Maître Splinter : Erreur de vision (API) : {e}"
            self.update_history(role="assistant", content=error_msg)
            return error_msg


    # --- Logique de Quiz ---

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
        
        try:
            quiz_context = self.read_file(self.QUIZ_CONTEXT_PATH)
        except FileNotFoundError:
            quiz_context = "Vous êtes un expert en formatage JSON strict. Répondez UNIQUEMENT avec le tableau JSON demandé."

        messages_to_send = [
            {"role": "system", "content": quiz_context},
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
            
        except (json.JSONDecodeError, Exception) as e:
            print(f"Erreur de génération/parsing du quiz: {e}")
            return False 

    def get_correction_for_final_review(self, question_data: dict, user_answer: str, model="llama3-70b-8192"):
        """
        Évalue la réponse de l'étudiant à la fin du quiz, en utilisant l'IA pour les questions ouvertes.
        Retourne un dictionnaire {"score": int, "feedback": str}.
        """
        
        q_type = question_data['type']
        correct_identifier = question_data['correct_identifier']
        explanation = question_data['explanation']
        
        teacher_context = self.read_file(self.TEACHER_CONTEXT_PATH)
        
        if q_type == 'qcm':
            score = 1 if user_answer.strip().upper() == correct_identifier.strip().upper() else 0
            
            if score == 1:
                feedback = f"⭐ Maître Splinter : Félicitations ! Votre choix est exact. Vous avez le regard affûté."
            else:
                feedback = f"❌ Maître Splinter : C'est un pas dans l'ombre. La bonne réponse était '{correct_identifier}'. Méditez sur cette explication : {explanation}"
                
            return {"score": score, "feedback": feedback}

        
        else:
            
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
                
                # Nettoyage JSON
                if raw_response.strip().startswith("```json"):
                    raw_response = raw_response.strip().strip("```json").strip("```").strip()

                return json.loads(raw_response)
            
            except json.JSONDecodeError as e:
                return {"score": 0, "feedback": f"❌ Maître Splinter : La concentration m'échappe. Le format de correction est rompu. Reprends ta pratique, jeune élève. (Détails: {raw_response[:50]}...)"}
            except Exception as e:
                return {"score": 0, "feedback": f"❌ Maître Splinter : Une erreur API est survenue. Méditez sur la discipline du code. Détails: {e}"}

