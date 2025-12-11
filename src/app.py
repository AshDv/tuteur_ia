import streamlit as st
from groq import Groq
from dotenv import load_dotenv
import os

# --- BACKEND : Le Cerveau de Splinter ---
class ConversationAgent:
    def __init__(self):
        load_dotenv()
        api_key = os.environ.get("GROQ_KEY")
        if not api_key:
            st.error("Clé API introuvable. Vérifie ton fichier .env")
            st.stop()
        self.client = Groq(api_key=api_key)

    def generate_response(self, messages):
        """Envoie l'historique de conversation à Groq et récupère la réponse"""
        try:
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                # MISE À JOUR : On utilise le dernier modèle Llama 3.3
                model="llama-3.3-70b-versatile", 
                temperature=0.7,
                max_tokens=1024, # Limite la longueur de la réponse pour éviter qu'il parle trop
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            return f"Erreur lors de la génération : {e}"

# --- FRONTEND : L'interface Streamlit ---

# 1. Configuration de la page
st.set_page_config(page_title="Splinter - Tuteur IA", page_icon="🐭")
st.title("🐭 Splinter - Ton Tuteur IA")

# 2. Initialisation de l'historique (Mémoire de session)
if "messages" not in st.session_state:
    st.session_state.messages = [
        # Le System Prompt définit la personnalité de Splinter
        {"role": "system", "content": "Tu es Splinter, un tuteur sage, patient et pédagogue. Tu aides les étudiants à réviser. Tu es concis mais précis."}
    ]

# 3. Affichage des anciens messages (sauf le système)
for message in st.session_state.messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# 4. Zone de saisie utilisateur
if prompt := st.chat_input("Pose ta question à Splinter..."):
    # A. Afficher le message de l'utilisateur
    with st.chat_message("user"):
        st.markdown(prompt)
    # B. Ajouter à l'historique
    st.session_state.messages.append({"role": "user", "content": prompt})

    # C. Générer la réponse de l'IA
    agent = ConversationAgent() # On instancie ta classe
    
    with st.chat_message("assistant"):
        with st.spinner("Splinter réfléchit..."):
            response = agent.generate_response(st.session_state.messages)
            st.markdown(response)
    
    # D. Sauvegarder la réponse de l'IA
    st.session_state.messages.append({"role": "assistant", "content": response})