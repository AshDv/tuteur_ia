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
    QUIZ_CONTEXT_PATH = os.path.join(os.path.dirname(__file__) + '/../resources/quiz_context.txt')

    def __init__(self, quiz_agent: QuizAgent):
        api_key = os.environ.get("GROQ_KEY")
        if not api_key:
            raise ValueError("GROQ_KEY non trouvée dans les variables d'environnement.")
            
        self.client = Groq(api_key=api_key)
        self.quiz_agent = quiz_agent
        self.initiate_history()

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

    def update_history(self, role, content, image_url=None):
        message_data = {"role": role, "content": content}
        if image_url:
            message_data["image_url"] = image_url 
        self.history.append(message_data)
        
    def get_history(self):
        return self.history

    def get_cleaned_api_history(self, include_multimodal_content=False, current_multimodal_content=None):
        messages_to_send = copy.deepcopy(self.history)
        
        for message in messages_to_send:
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
        
        return messages_to_send

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

    def ask_vision_model(self, user_interaction, images_data, model):

        multimodal_content_api = [{"type": "text", "text": user_interaction}]

        for img in images_data:
            multimodal_content_api.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img['mime']};base64,{img['b64']}",
                },
            })

        first_display_url = images_data[0]['display_url'] if images_data else None
        
        self.update_history(
            role="user", 
            content=user_interaction,
            image_url=first_display_url 
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

    def generate_quiz(self, topic, n_questions, model, difficulty, context_instruction):
        
        prompt_quiz = f"""
            Tu es un professeur expert. Sujet : "{topic}". Niveau : {difficulty}.
            Objectif : Générer EXACTEMENT {n_questions} questions.
            {context_instruction}
            
            INSTRUCTIONS :
            Génère {n_questions} questions variées ('open' et 'qcm').
            Si le texte est court, interroge sur des détails précis.
            
            Réponds UNIQUEMENT avec un tableau JSON valide (liste d'objets) respectant le schéma imposé dans le prompt système. 
            
            Exemple de format JSON STRICTEMENT requis pour la clé "questions" du tableau :
            [
                {{
                    "type": "qcm",
                    "question": "L'énoncé ?",
                    "explanation": "Pourquoi c'est juste",
                    "correct_identifier": "A",
                    "choices": ["A. Option 1", "B. Option 2", "C. Option 3", "D. Option 4"]
                }}
            ]
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

        except json.JSONDecodeError as e:
            error_message = f"Erreur de décodage JSON: Le LLM n'a pas retourné un format valide. Détails: {e}. Réponse brute reçue: {raw_response[:200]}..."
            print(f"[LOG CONSOLE - QUIZ GENERATION ERROR] {error_message}")
            return error_message
        
        except Exception as e:
            error_message = f"Erreur API/Réseau: Échec de la connexion à Groq ou erreur interne. Détails: {e}"
            print(f"[LOG CONSOLE - QUIZ GENERATION ERROR] {error_message}")
            return error_message

    def get_correction_for_final_review(
            self, 
            question_data: dict, 
            user_answer: str, 
            model="openai/gpt-oss-120b"
        ):
        
        q_type = question_data['type']
        correct_identifier = question_data['correct_identifier']
        explanation = question_data['explanation']
        
        if not correct_identifier or not q_type:
            return {
                "score": 0, 
                "feedback": f"❌ Le format de la question est brisé (Données manquantes).",
                "error_details": question_data
            }
        
        teacher_context = self.read_file(self.TEACHER_CONTEXT_PATH)
        
        if q_type == 'qcm':
            score = 1 if user_answer.strip().upper() == correct_identifier.strip().upper() else 0
            
            if score == 1:
                feedback = f"⭐ Félicitations ! Votre choix est exact. Vous avez le regard affûté."
            else:
                feedback = f"❌ C'est un pas dans l'ombre. La bonne réponse était '{correct_identifier}'. Méditez sur cette explication : {explanation}"
                
            return {"score": score, "feedback": feedback}
        
        else:
            
            prompt_correction = f"""
            TACHE : En tant que Maître Splinter, évalue la réponse de l'étudiant.
            
            Réponse attendue (Référence pour la notation) : '{correct_identifier}'
            Réponse de l'étudiant : '{user_answer}'
            
            [Explication détaillée fournie si besoin : {explanation}]
            
            RÈGLE DE NOTATION (MODE TRÈS INDULGENT) :
            1. L'objectif est la validation des acquis. Si la réponse touche à UN SEUL aspect correct du concept, elle doit être considérée comme VALIDE (Score 1).
            2. Soyez extrêmement tolérant. Ne pénalisez pas le manque de précision ou l'oubli de détails si une partie de la réponse est juste.
            
            RÈGLE DE NOTATION FORMELLE :
            * Score 1 (CORRECT) : La réponse mentionne au moins un élément pertinent, un mot-clé correct ou une idée liée à la réponse attendue, même si elle est incomplète ou vague.
            * Score 0 (INCORRECT) : La réponse est un contresens total, parle d'un autre sujet, ou est vide.
            
            3. Le 'feedback' doit être formulé avec le ton sage et pédagogique de Maître Splinter. Si la réponse est validée mais incomplète, dites "Bien joué" et ajoutez simplement les détails manquants pour l'apprentissage.
            
            FORMAT DE SORTIE OBLIGATOIRE :
            Retourne UNIQUEMENT l'objet JSON suivant sans aucun texte supplémentaire :
            {{"score": (int, 0 ou 1), "feedback": (string formulé par Maître Splinter)}}
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
            
            except json.JSONDecodeError as e:
                return {"score": 0, "feedback": f"❌ Maître Splinter : La concentration m'échappe. Le format de correction est rompu. Reprends ta pratique, jeune élève. (Détails: {raw_response[:50]}...)"}
            except Exception as e:
                return {"score": 0, "feedback": f"❌ Maître Splinter : Une erreur API est survenue. Méditez sur la discipline du code. Détails: {e}"}