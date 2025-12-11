import streamlit as st
import PyPDF2
import base64

class DocumentProcessor:
    """Gère l'extraction de texte et l'encodage d'images."""

    @staticmethod
    def extract_text_from_pdf(pdf_file) -> str:
        """Lit un fichier PDF et retourne son contenu textuel."""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text_content = ""
            for page in pdf_reader.pages:
                extracted_text = page.extract_text()
                if extracted_text:
                    text_content += extracted_text + "\n"
            return text_content
        except Exception as e:
            st.error(f"Erreur lors de la lecture du PDF : {e}")
            return ""

    @staticmethod
    def convert_image_to_base64(image_file) -> str | None:
        """Convertit une image uploadée en chaîne Base64 pour l'API."""
        if image_file is None:
            return None
        try:
            image_file.seek(0)
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return f"data:{image_file.type};base64,{encoded_string}"
        except Exception as e:
            st.error(f"Erreur d'encodage de l'image : {e}")
            return None