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
            ---

            INSTRUCTIONS DE GÉNÉRATION :
            1.  Crée EXACTEMENT {n_questions} questions.
            2.  Assure une VARIÉTÉ dans les types de questions ('open' pour les concepts détaillés, 'qcm' pour la mémorisation).
            3.  Chaque question doit être indépendante du contexte d'une autre.
            4.  La clé "explanation" doit contenir l'explication complète et pédagogique de la solution, même pour les questions ouvertes.
            5.  La langue utilisé pour les question et réponses doit UNIQUEMENT être du français.
            
            FORMAT IMPÉRATIF :
            Réponds UNIQUEMENT avec un tableau JSON (liste Python) respectant le schéma suivant et les contraintes de clés fournies dans le prompt système.

            POUR CHAQUE QUESTION 'qcm' :
            -   "type": "qcm"
            -   "choices": Une liste de 4 options (A, B, C, D)
            -   "correct_identifier": La lettre majuscule correcte (A, B, C ou D)

            POUR CHAQUE QUESTION 'open' :
            -   "type": "open"
            -   "correct_identifier": La réponse détaillée et complète attendue pour la correction.
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
            # --- LOGIQUE AMÉLIORÉE : Récupération du texte complet ---
            choices = question_data.get('choices', [])
            full_correct_answer = correct_identifier # Valeur par défaut (la lettre)
            
            # On cherche l'option qui commence par la bonne lettre (ex: "A.")
            if choices:
                for choice in choices:
                    if choice.strip().upper().startswith(correct_identifier.strip().upper()):
                        full_correct_answer = choice
                        break
            
            # Calcul du score
            score = 1 if user_answer.strip().upper() == correct_identifier.strip().upper() else 0
            
            # Construction du feedback clair et complet
            if score == 1:
                feedback = f"✅ **Correct !**\n\nVous avez bien identifié la réponse : **{full_correct_answer}**.\n\n💡 *{explanation}*"
            else:
                feedback = f"❌ **Incorrect.**\n\nLa bonne réponse est : **{full_correct_answer}**.\n\n💡 **Explication :** {explanation}"
                
            return {"score": score, "feedback": feedback}
        
        else:
            # Pour les questions ouvertes, on garde la logique LLM mais on force un format direct
            prompt_correction = f"""
            TACHE : Corrige cette réponse d'étudiant de manière DIRECTE et CONCISE.
            
            Question : {question_data.get('question')}
            Réponse attendue : '{correct_identifier}'
            Réponse de l'étudiant : '{user_answer}'
            Explication contextuelle : {explanation}
            
            RÈGLES :
            1. Si la réponse est juste (sens globalement identique), mets score 1. Sinon 0.
            2. Ton feedback doit commencer directement par "Correct" ou "Incorrect".
            3. Donne ensuite la bonne réponse CLAIREMENT sans fioritures.
            4. Finis par une explication simple.
            
            FORMAT DE SORTIE OBLIGATOIRE (JSON pur) :
            {{"score": (int, 0 ou 1), "feedback": (string)}}
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
                return {"score": 0, "feedback": f"❌ Erreur de formatage de la correction. (Détails: {raw_response[:50]}...)"}
            except Exception as e:
                return {"score": 0, "feedback": f"❌ Erreur API pendant la correction. Détails: {e}"}