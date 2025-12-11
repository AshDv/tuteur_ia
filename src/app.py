import streamlit as st
from groq import Groq
from dotenv import load_dotenv
import os
import json
import PyPDF2
import base64

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

def encode_image(image_file):
    """Encode une image uploadée en chaîne base64."""
    if image_file is not None:
        try:
            image_file.seek(0)
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return f"data:{image_file.type};base64,{encoded_string}"
        except Exception as e:
            st.error(f"Erreur d'encodage image : {e}")
            return None
    return None

# --- BACKEND : Le Cerveau de Splinter ---
class ConversationAgent:
    def __init__(self):
        load_dotenv()
        api_key = os.environ.get("GROQ_KEY")
        if not api_key:
            st.error("Clé API introuvable. Vérifie ton fichier .env")
            st.stop()
        self.client = Groq(api_key=api_key)

    def generate_response(self, messages, context_text=None, image_data_url=None):
        # 1. Choix du modèle
        if image_data_url:
            # ✅ Modèle Vision Llama 4 Scout (choisi par l'utilisateur)
            model_id = "meta-llama/llama-4-scout-17b-16e-instruct"
            max_tok = 1024
        else:
            # Modèle Texte standard
            model_id = "llama-3.3-70b-versatile"
            max_tok = 2048

        # 2. Contexte
        system_prompt = "Tu es Splinter, un tuteur pédagogue."
        if context_text:
            system_prompt += f" Utilise le cours ci-dessous si pertinent.\n\n--- COURS ---\n{context_text[:25000]}"
        
        # 3. Construction des messages
        api_messages = [{"role": "system", "content": system_prompt}]
        
        last_user_message = None
        for msg in messages:
            if msg["role"] == "user":
                last_user_message = msg["content"]
            else:
                api_messages.append(msg)
        
        # 4. Ajout du dernier message (Texte + Image potentielle)
        if image_data_url and last_user_message:
            user_content = [
                {"type": "text", "text": last_user_message},
                {
                    "type": "image_url", 
                    "image_url": {"url": image_data_url}
                }
            ]
            api_messages.append({"role": "user", "content": user_content})
        elif last_user_message:
            api_messages.append({"role": "user", "content": last_user_message})
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=api_messages,
                model=model_id,
                temperature=0.7,
                max_tokens=max_tok,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            return f"Erreur API ({model_id}) : {e}"

    def generate_quiz(self, topic, difficulty, num_questions, context_text=None):
        context_instruction = ""
        if context_text:
            context_instruction = f"Base tes questions EXCLUSIVEMENT sur le cours suivant :\n{context_text[:20000]}"
        
        prompt = f"""
        Tu es un professeur expert qui crée un examen.
        Sujet : "{topic}". Niveau : {difficulty}.
        Objectif : Générer EXACTEMENT {num_questions} questions.
        {context_instruction}
        INSTRUCTIONS STRICTES :
        1. Tu DOIS générer {num_questions} questions. Pas moins.
        2. Si le texte est court, interroge sur des détails ou définitions pour atteindre le chiffre {num_questions}.
        3. Varie le type de questions.
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
                max_tokens=4096, 
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            st.error(f"Erreur génération quiz : {e}")
            return None

# --- FRONTEND ---
st.set_page_config(page_title="Splinter - Tuteur IA", page_icon="🐭", layout="wide")

# -- SIDEBAR --
with st.sidebar:
    st.image("https://img.icons8.com/dusk/64/000000/rat.png")
    st.title("📚 Tes Documents")
    
    # PDF Upload
    uploaded_pdf = st.file_uploader("Fichier PDF (Cours)", type="pdf", key="pdf_uploader")
    course_content = ""
    if uploaded_pdf is not None:
        with st.spinner("Analyse du PDF..."):
            course_content = extract_text_from_pdf(uploaded_pdf)
            st.success(f"PDF chargé ! ({len(course_content)} chars)")

    st.divider()

    # Image Upload
    st.title("🖼️ Image à analyser")
    uploaded_image = st.file_uploader("Image (Schéma, Graphique...)", type=["png", "jpg", "jpeg"], key="img_uploader")
    
    image_data_url = None
    if uploaded_image is not None:
        st.image(uploaded_image, caption="Image chargée", use_container_width=True)
        
        with st.spinner("Préparation de l'image..."):
            image_data_url = encode_image(uploaded_image)
            if image_data_url:
                 st.success("Image prête à être envoyée !")

st.title("🐭 Splinter - Tuteur IA")

tab1, tab2 = st.tabs(["💬 Discussion & Vision", "📝 Quiz Dynamique"])

# --- TAB 1 : CHAT ---
with tab1:
    chat_container = st.container()
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    with chat_container:
        if course_content and st.button("📑 Résumer ce cours"):
            st.session_state.messages.append({"role": "user", "content": "Résume ce cours en détail."})
            st.rerun()

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input("Pose ta question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        agent = ConversationAgent()
        
        with st.spinner("Analyse en cours..."):
            response = agent.generate_response(
                st.session_state.messages, 
                context_text=course_content,
                image_data_url=image_data_url
            )
        
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

# --- TAB 2 : QUIZ ---
with tab2:
    st.header("Mode Évaluation")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        default_topic = "Le cours complet ci-joint" if course_content else ""
        topic = st.text_input("Sujet à évaluer", value=default_topic)
    with col2:
        difficulty = st.selectbox("Niveau", ["Débutant", "Moyen", "Expert"])
    with col3:
        num_questions = st.slider("Nombre de questions (Cible)", min_value=1, max_value=20, value=5)

    if st.button("Générer l'évaluation") and topic:
        agent = ConversationAgent()
        with st.spinner(f"Génération de {num_questions} questions en cours..."):
            quiz_data = agent.generate_quiz(topic, difficulty, num_questions, context_text=course_content)
            if quiz_data:
                st.session_state.current_quiz = quiz_data
                st.session_state.user_answers = {} 
                st.session_state.quiz_submitted = False
                st.rerun()

    if "current_quiz" in st.session_state:
        quiz = st.session_state.current_quiz
        nb_questions_generated = len(quiz["questions"])
        
        if nb_questions_generated < num_questions:
            st.warning(f"Généré : {nb_questions_generated} / Cible : {num_questions}")
        else:
            st.success(f"Quiz de {nb_questions_generated} questions généré !")

        with st.form("quiz_form"):
            for i, q in enumerate(quiz["questions"]):
                st.markdown(f"**Q{i+1} :** {q['question']}")
                st.radio("Votre réponse :", q["options"], key=f"q_{i}", index=None, label_visibility="collapsed")
                st.write("---")
            
            if st.form_submit_button("Valider mes réponses"):
                st.session_state.quiz_submitted = True
                st.rerun()

        if st.session_state.get("quiz_submitted"):
            st.divider()
            score = 0
            for i, q in enumerate(quiz["questions"]):
                user_choice = st.session_state.get(f"q_{i}")
                if user_choice == q["correct_answer"]:
                    score += 1
                    st.success(f"✅ Q{i+1}")
                else:
                    st.error(f"❌ Q{i+1} ({user_choice})")
                    st.caption(f"👉 {q['correct_answer']} | {q['explanation']}")
            
            final_score = (score / nb_questions_generated) * 20
            st.markdown(f"### 🏆 Note : {score}/{nb_questions_generated} ({final_score:.1f}/20)")