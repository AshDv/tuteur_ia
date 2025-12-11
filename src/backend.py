import os
import json
import streamlit as st
from groq import Groq
from dotenv import load_dotenv

class SplinterBrain:
    """Gère toutes les interactions avec l'API Groq (Cerveau de l'IA)."""

    def __init__(self):
        load_dotenv()
        api_key = os.environ.get("GROQ_KEY")
        if not api_key:
            st.error("❌ Clé API introuvable. Veuillez vérifier votre fichier .env")
            st.stop()
        self.client = Groq(api_key=api_key)

    def _get_model_id(self, has_image: bool) -> tuple[str, int]:
        """Retourne l'ID du modèle et la limite de tokens selon le contexte."""
        if has_image:
            # Modèle Vision (Llama 4 Scout)
            return "meta-llama/llama-4-scout-17b-16e-instruct", 1024
        else:
            # Modèle Texte Standard
            return "llama-3.3-70b-versatile", 2048

    def _build_system_prompt(self, context_text: str = None) -> str:
        """Construit le prompt système avec ou sans contexte pédagogique."""
        base_prompt = "Tu es Splinter, un tuteur pédagogue, sage et patient."
        if context_text:
            return f"{base_prompt} Utilise le cours ci-dessous pour répondre.\n\n--- COURS ---\n{context_text[:25000]}"
        return base_prompt

    def generate_chat_response(self, message_history: list, context_text: str = None, image_url: str = None) -> str:
        """Génère une réponse textuelle (avec ou sans vision)."""
        model_id, max_tokens = self._get_model_id(has_image=bool(image_url))
        
        # Préparation des messages
        system_message = {"role": "system", "content": self._build_system_prompt(context_text)}
        api_messages = [system_message]

        # Traitement de l'historique
        last_user_content = ""
        for msg in message_history:
            if msg["role"] == "user":
                last_user_content = msg["content"]
            else:
                api_messages.append(msg)

        # Ajout du dernier message utilisateur (Texte + Image potentielle)
        if image_url:
            final_user_message = {
                "role": "user",
                "content": [
                    {"type": "text", "text": last_user_content},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
            api_messages.append(final_user_message)
        elif last_user_content:
            api_messages.append({"role": "user", "content": last_user_content})

        try:
            response = self.client.chat.completions.create(
                messages=api_messages,
                model=model_id,
                temperature=0.7,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"🚨 Erreur API ({model_id}) : {e}"

    def generate_quiz_json(self, topic: str, difficulty: str, num_questions: int, context_text: str = None) -> dict:
        """Génère un quiz structuré au format JSON."""
        context_instruction = ""
        if context_text:
            context_instruction = f"Base tes questions EXCLUSIVEMENT sur ce cours :\n{context_text[:20000]}"

        prompt = f"""
        Tu es un professeur expert. Sujet : "{topic}". Niveau : {difficulty}.
        Objectif : Générer EXACTEMENT {num_questions} questions.
        {context_instruction}
        
        INSTRUCTIONS :
        1. Génère {num_questions} questions variées (QCM).
        2. Si le texte est court, interroge sur des détails précis.
        
        Réponds UNIQUEMENT avec un JSON valide :
        {{
            "questions": [
                {{
                    "question": "L'énoncé ?",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "La réponse complète",
                    "explanation": "Pourquoi c'est juste"
                }}
            ]
        }}
        """
        try:
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.5,
                max_tokens=4096,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            st.error(f"Erreur de génération du quiz : {e}")
            return None