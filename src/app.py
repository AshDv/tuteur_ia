import streamlit as st
from groq import Groq
from dotenv import load_dotenv
import os
import json

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
        """Gère la conversation normale"""
        try:
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=1024,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            return f"Erreur : {e}"

    def generate_quiz(self, topic, difficulty="Moyen"):
        """Génère un quiz structuré en JSON"""
        # On force l'IA à répondre en JSON strict pour pouvoir corriger automatiquement
        prompt = f"""
        Tu es un générateur de quiz éducatif. Génère un QCM de 5 questions sur le sujet : "{topic}".
        Niveau : {difficulty}.
        
        IMPORTANT : Ta réponse doit être UNIQUEMENT un objet JSON valide, sans texte avant ni après.
        Voici le format exact attendu :
        {{
            "questions": [
                {{
                    "question": "L'énoncé de la question ?",
                    "options": ["Choix A", "Choix B", "Choix C", "Choix D"],
                    "correct_answer": "Choix B",
                    "explanation": "Pourquoi c'est la bonne réponse."
                }}
            ]
        }}
        """
        try:
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.5, # Plus bas pour être plus rigoureux
                response_format={"type": "json_object"} # Force le mode JSON
            )
            # On transforme le texte reçu en objet Python (Dictionnaire)
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            st.error(f"Erreur lors de la génération du quiz : {e}")
            return None

# --- FRONTEND : L'interface Streamlit ---

st.set_page_config(page_title="Splinter - Tuteur IA", page_icon="🐭")
st.title("🐭 Splinter - Ton Tuteur IA")

# Création des onglets
tab1, tab2 = st.tabs(["💬 Discussion", "📝 Quiz Interactif"])

# --- ONGLET 1 : CHAT ---
with tab1:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "system", "content": "Tu es Splinter, un tuteur sage. Tu aides à réviser."}
        ]

    for message in st.session_state.messages:
        if message["role"] != "system":
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input("Pose ta question à Splinter..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        agent = ConversationAgent()
        with st.chat_message("assistant"):
            with st.spinner("Splinter réfléchit..."):
                response = agent.generate_response(st.session_state.messages)
                st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

# --- ONGLET 2 : QUIZ ---
with tab2:
    st.header("Mode Évaluation")
    
    # 1. Configuration du quiz
    col1, col2 = st.columns([3, 1])
    with col1:
        topic = st.text_input("Sur quel sujet veux-tu être testé ?", placeholder="Ex: La Révolution Française, Python, La Photosynthèse...")
    with col2:
        difficulty = st.selectbox("Difficulté", ["Débutant", "Moyen", "Expert"])

    # Bouton pour lancer la génération
    if st.button("Générer le Quiz") and topic:
        agent = ConversationAgent()
        with st.spinner("Splinter prépare tes questions..."):
            quiz_data = agent.generate_quiz(topic, difficulty)
            if quiz_data:
                # On sauvegarde le quiz dans la mémoire (session_state)
                st.session_state.current_quiz = quiz_data
                # On efface les réponses précédentes s'il y en avait
                st.session_state.user_answers = {} 
                st.session_state.quiz_submitted = False

    # 2. Affichage du quiz (s'il existe en mémoire)
    if "current_quiz" in st.session_state:
        quiz = st.session_state.current_quiz
        
        # Formulaire pour éviter que la page se recharge à chaque clic
        with st.form("quiz_form"):
            for i, q in enumerate(quiz["questions"]):
                st.subheader(f"Question {i+1}")
                st.write(q["question"])
                
                # Le widget radio pour les choix
                # On utilise un key unique pour chaque question
                choice = st.radio(
                    "Ton choix :", 
                    q["options"], 
                    key=f"q_{i}", 
                    index=None # Aucun choix sélectionné par défaut
                )
            
            submitted = st.form_submit_button("Valider mes réponses")
            
            if submitted:
                st.session_state.quiz_submitted = True

        # 3. Correction et Note
        if st.session_state.get("quiz_submitted"):
            score = 0
            total = len(quiz["questions"])
            
            st.divider()
            st.markdown("### 📊 Résultats")
            
            for i, q in enumerate(quiz["questions"]):
                user_choice = st.session_state.get(f"q_{i}")
                correct = q["correct_answer"]
                
                if user_choice == correct:
                    score += 1
                    st.success(f"✅ **Question {i+1}** : Bravo ! (Réponse : {correct})")
                else:
                    st.error(f"❌ **Question {i+1}** : Faux. Tu as mis '{user_choice}'.")
                    st.info(f"👉 **La bonne réponse était** : {correct}\n\n💡 *Explication : {q['explanation']}*")
            
            # Affichage de la note finale
            final_score = (score / total) * 20
            st.markdown(f"## Note finale : {score}/{total} ({final_score:.1f}/20)")
            
            if final_score > 15:
                st.balloons()
                st.markdown("🏆 Excellent travail jeune padawan !")
            elif final_score > 10:
                st.markdown("👍 Pas mal, mais tu peux encore réviser.")
            else:
                st.markdown("📚 Il va falloir retourner étudier ce sujet !")