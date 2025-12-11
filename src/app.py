import streamlit as st
from groq import Groq
from dotenv import load_dotenv
import os
import json
import PyPDF2

# --- FONCTIONS UTILITAIRES ---
def extract_text_from_pdf(pdf_file):
    """Extrait le texte brut d'un fichier PDF uploadé"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"
        return text
    except Exception as e:
        return f"Erreur de lecture PDF : {e}"

# --- BACKEND : Le Cerveau de Splinter ---
class ConversationAgent:
    def __init__(self):
        load_dotenv()
        api_key = os.environ.get("GROQ_KEY")
        if not api_key:
            st.error("Clé API introuvable. Vérifie ton fichier .env")
            st.stop()
        self.client = Groq(api_key=api_key)

    def generate_response(self, messages, context_text=None):
        if context_text:
            system_message_content = (
                "Tu es Splinter, un tuteur pédagogue. "
                "Utilise le cours fourni ci-dessous pour répondre. "
                "Si la réponse n'est pas dans le cours, utilise tes connaissances.\n\n"
                f"--- COURS ---\n{context_text[:20000]}"
            )
            # On insère le contexte au début sans écraser l'historique complet
            messages_with_context = [{"role": "system", "content": system_message_content}] + messages
        else:
            messages_with_context = messages

        try:
            chat_completion = self.client.chat.completions.create(
                messages=messages_with_context,
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=1024,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            return f"Erreur : {e}"

    def generate_quiz(self, topic, difficulty="Moyen", context_text=None):
        context_instruction = ""
        if context_text:
            context_instruction = f"IMPORTANT : Base tes questions EXCLUSIVEMENT sur le cours suivant :\n{context_text[:15000]}"
        
        prompt = f"""
        Génère un QCM de 5 questions sur : "{topic}". Niveau : {difficulty}.
        {context_instruction}
        Réponds UNIQUEMENT avec un JSON valide :
        {{
            "questions": [
                {{
                    "question": "...",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "...",
                    "explanation": "..."
                }}
            ]
        }}
        """
        try:
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            st.error(f"Erreur génération quiz : {e}")
            return None

# --- FRONTEND : L'interface Streamlit ---
st.set_page_config(page_title="Splinter - Tuteur IA", page_icon="🐭", layout="wide")

# -- SIDEBAR --
with st.sidebar:
    st.image("https://img.icons8.com/dusk/64/000000/rat.png")
    st.title("📚 Tes Cours")
    uploaded_file = st.file_uploader("Fichier PDF", type="pdf")
    
    course_content = ""
    if uploaded_file is not None:
        with st.spinner("Lecture..."):
            course_content = extract_text_from_pdf(uploaded_file)
            st.success("Cours chargé !")

st.title("🐭 Splinter - Tuteur IA")

tab1, tab2 = st.tabs(["💬 Discussion", "📝 Quiz"])

# --- ONGLET 1 : CHAT (Corrigé) ---
with tab1:
    # Conteneur pour l'historique (S'affiche toujours au-dessus)
    chat_container = st.container()
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Affichage de l'historique
    with chat_container:
        if course_content and st.button("📑 Résumer ce cours"):
            st.session_state.messages.append({"role": "user", "content": "Résume ce cours."})
            st.rerun() # On recharge pour traiter la demande immédiatement

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # Zone de saisie (Toujours en bas)
    if prompt := st.chat_input("Pose ta question..."):
        # 1. Sauvegarder la question de l'utilisateur
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # 2. Générer la réponse
        agent = ConversationAgent()
        response = agent.generate_response(st.session_state.messages, context_text=course_content)
        
        # 3. Sauvegarder la réponse
        st.session_state.messages.append({"role": "assistant", "content": response})
        
        # 4. RECHARGER LA PAGE (C'est la clé du fix !)
        st.rerun()

# --- ONGLET 2 : QUIZ ---
with tab2:
    st.header("Mode Évaluation")
    col1, col2 = st.columns([3, 1])
    with col1:
        default_topic = "Le cours ci-joint" if course_content else ""
        topic = st.text_input("Sujet", value=default_topic)
    with col2:
        difficulty = st.selectbox("Niveau", ["Débutant", "Moyen", "Expert"])

    if st.button("Générer le Quiz") and topic:
        agent = ConversationAgent()
        with st.spinner("Génération..."):
            quiz_data = agent.generate_quiz(topic, difficulty, context_text=course_content)
            if quiz_data:
                st.session_state.current_quiz = quiz_data
                st.session_state.user_answers = {} 
                st.session_state.quiz_submitted = False
                st.rerun()

    if "current_quiz" in st.session_state:
        quiz = st.session_state.current_quiz
        with st.form("quiz_form"):
            for i, q in enumerate(quiz["questions"]):
                st.subheader(f"Q{i+1}: {q['question']}")
                st.radio("Réponse", q["options"], key=f"q_{i}", index=None)
            
            if st.form_submit_button("Valider"):
                st.session_state.quiz_submitted = True
                st.rerun()

        if st.session_state.get("quiz_submitted"):
            st.divider()
            score = 0
            for i, q in enumerate(quiz["questions"]):
                user_choice = st.session_state.get(f"q_{i}")
                if user_choice == q["correct_answer"]:
                    score += 1
                    st.success(f"✅ Q{i+1} : Bravo !")
                else:
                    st.error(f"❌ Q{i+1} : Faux. ({user_choice})")
                    st.info(f"Réponse : {q['correct_answer']} | {q['explanation']}")
            st.markdown(f"### Note : {score}/{len(quiz['questions'])}")