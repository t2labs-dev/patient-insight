import streamlit as st
import pandas as pd
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from typing import List
from pydantic import BaseModel
from insight_extractor import InsightExtractor, Treatment, PatientInsights
from dotenv import load_dotenv

class TreatmentList(BaseModel):
    treatments: List[Treatment]

# Chargement des variables d'environnement
load_dotenv()

st.set_page_config(page_title="Patient Insight Extractor", layout="wide")

# Initialisation du session_state
if "insights" not in st.session_state:
    st.session_state.insights = None
if "comparison" not in st.session_state:
    st.session_state.comparison = None
if "patient_text" not in st.session_state:
    st.session_state.patient_text = ""

def reset_state():
    st.session_state.insights = None
    st.session_state.comparison = None
    st.session_state.patient_text = ""
    st.rerun()

def highlight_text(text, insights):
    """Simple HTML highlighter for medical terms and medications"""
    import re
    if not insights:
        return text
    
    terms_to_highlight = set()
    
    # Collect medications
    for t in (insights.traitements_habituels or []):
        terms_to_highlight.add(t.name)
    for t in (insights.traitement_sortie or []):
        terms_to_highlight.add(t.name)
    
    # Collect other terms (simple split)
    for ant in (insights.antecedents_medicaux or []):
        # Add the whole antecedent and also individual words if they look like medical terms
        terms_to_highlight.add(ant)
    
    if insights.raison_hospitalisation:
        terms_to_highlight.add(insights.raison_hospitalisation)

    # Sort terms by length descending to avoid partial matches inside larger matches
    sorted_terms = sorted([t for t in terms_to_highlight if t and len(t) > 2], key=len, reverse=True)
    
    highlighted = text.replace("\n", "<br>")
    
    for term in sorted_terms:
        # Case insensitive replacement with highlight
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        highlighted = pattern.sub(f'<span style="background-color: #ffff00; color: black; font-weight: bold;">\g<0></span>', highlighted)
        
    return highlighted

# Layout de l'en-tête
col_title, col_reset = st.columns([4, 1])
with col_title:
    st.title("👨‍⚕️ Extracteur d'Insights Patient")
with col_reset:
    st.button("🆕 Nouveau cas", on_click=reset_state)

st.markdown("""
Cette application utilise l'IA pour extraire des informations structurées à partir de comptes-rendus médicaux.
""")

# Configuration du modèle dans la barre latérale
st.sidebar.header("Configuration")
model_provider = st.sidebar.selectbox("Provider", ["openai", "ollama", "mistral"], 
                                    index=["openai", "ollama", "mistral"].index(os.getenv("MODEL_PROVIDER", "openai")))
model_name = st.sidebar.text_input("Modèle", value=os.getenv("MODEL_NAME", "gpt-4o"))

# Initialisation de l'extracteur
@st.cache_resource
def get_extractor(provider, name):
    return InsightExtractor(model_provider=provider, model_name=name)

extractor = get_extractor(model_provider, model_name)

# --- LOGIQUE D'AFFICHAGE ---
if st.session_state.insights is None:
    # Zone de saisie initiale
    st.subheader("Compte-rendu Médical")
    patient_input = st.text_area("Collez ici le texte du patient :", height=300, 
                               placeholder="Antécédents : ...\nTraitements : ...",
                               key="patient_input_area")
    
    if st.button("Extraire les Insights"):
        if not patient_input.strip():
            st.warning("Veuillez entrer du texte avant de lancer l'extraction.")
        else:
            with st.spinner("Analyse du texte par l'IA en cours..."):
                try:
                    res_insights = extractor.extract_from_text(patient_input)
                    st.session_state.insights = res_insights
                    st.session_state.patient_text = patient_input
                    st.rerun()
                except Exception as e:
                    st.error(f"Une erreur est survenue : {e}")
                    if model_provider == "openai":
                        st.info("Vérifiez votre clé API OpenAI dans le fichier .env")
                    elif model_provider == "ollama":
                        st.info("Assurez-vous qu'Ollama est lancé localement et que le modèle est disponible.")
                    elif model_provider == "mistral":
                        st.info("Vérifiez votre clé API Mistral dans le fichier .env")
else:
    # Affichage des résultats
    insights = st.session_state.insights
    st.success("Extraction terminée !")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🏥 Informations Générales")
        age_val = getattr(insights, "age", None)
        sexe_val = getattr(insights, "sexe", None)
        st.markdown(f"**Âge :** {age_val if age_val else 'N/A'} ans")
        st.markdown(f"**Sexe :** {sexe_val if sexe_val else 'N/A'}")
        st.markdown(f"**Pourquoi il est hospitalisé :**\n{insights.raison_hospitalisation}")
        st.markdown("**Antécédents médicaux :**")
        for ant in insights.antecedents_medicaux:
            st.markdown(f"- {ant}")
        
    with col2:
        st.markdown("### 🧬 Fonctions Organiques")
        st.info(f"**Fonction rénale :**\n{insights.fonction_renale}")
        st.info(f"**Fonction hépatique :**\n{insights.fonction_hepatique}")

    # Section Comparaison
    st.markdown("---")
    st.markdown("### 🔍 Comparaison avec une nouvelle prescription")
    new_presc_input = st.text_area("Nouvelle prescription :", 
                                 placeholder="Ex: Zestryl 10mg le matin\nDoliprane 1g 3 fois par jour",
                                 key="new_presc_area")
    
    if st.button("Comparer avec la nouvelle prescription"):
        if not new_presc_input.strip():
            st.warning("Veuillez entrer une nouvelle prescription à comparer.")
        else:
            with st.spinner("Analyse de la comparaison..."):
                parser = PydanticOutputParser(pydantic_object=TreatmentList)
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "Tu es un assistant médical. Extrait la liste des médicaments de cette prescription.\n{format_instructions}"),
                    ("user", "{text}")
                ])
                try:
                    structured_llm = extractor.llm.with_structured_output(TreatmentList)
                    chain = prompt | structured_llm
                    res = chain.invoke({"text": new_presc_input, "format_instructions": parser.get_format_instructions()})
                    new_treatments = res.treatments
                except:
                    chain = prompt | extractor.llm | parser
                    res = chain.invoke({"text": new_presc_input, "format_instructions": parser.get_format_instructions()})
                    new_treatments = res.treatments

                st.session_state.comparison = extractor.compare_prescription(insights, new_treatments)

    if st.session_state.comparison:
        comp = st.session_state.comparison
        st.markdown("#### Résultats de la comparaison")
        df_comp = pd.DataFrame([
            {"Médicament": c.medication_name, "Statut": c.status, "Détails": c.details} 
            for c in comp.comparisons
        ])
        st.table(df_comp)
        
        st.markdown("#### Recommandations")
        for rec in comp.recommendations:
            st.warning(rec)

    st.markdown("---")
    st.markdown("### 💊 Traitements Habituels")
    if insights.traitements_habituels:
        data_hab = []
        for t in insights.traitements_habituels:
            row = t.model_dump()
            row["Vidal"] = f"https://www.vidal.fr/recherche.html?query={t.name}"
            data_hab.append(row)
        
        df_hab = pd.DataFrame(data_hab)
        df_hab.columns = ["Médicament", "Dosage", "Fréquence", "Lien Vidal"]
        st.dataframe(
            df_hab,
            column_config={
                "Lien Vidal": st.column_config.LinkColumn(
                    "Recherche Vidal",
                    help="Chercher sur Vidal.fr",
                    validate=r"^https://www\.vidal\.fr/.*",
                    display_text="Chercher ↗️"
                ),
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.write("Aucun traitement habituel détecté.")

    st.markdown("### 📋 Traitement de Sortie")
    if insights.traitement_sortie:
        data_sortie = []
        for t in insights.traitement_sortie:
            row = t.model_dump()
            row["Vidal"] = f"https://www.vidal.fr/recherche.html?query={t.name}"
            data_sortie.append(row)
            
        df_sortie = pd.DataFrame(data_sortie)
        df_sortie.columns = ["Médicament", "Dosage", "Fréquence", "Lien Vidal"]
        st.dataframe(
            df_sortie,
            column_config={
                "Lien Vidal": st.column_config.LinkColumn(
                    "Recherche Vidal",
                    help="Chercher sur Vidal.fr",
                    validate=r"^https://www\.vidal\.fr/.*",
                    display_text="Chercher ↗️"
                ),
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.write("Aucun traitement de sortie détecté.")

    # Affichage du texte original bien formaté et surligné
    st.markdown("---")
    st.markdown("### 📝 Texte Original Surligné")
    highlighted_html = highlight_text(st.session_state.patient_text, insights)
    st.markdown(f"""
        <div style="padding: 20px; border-radius: 10px; font-family: sans-serif; line-height: 1.6;">
            {highlighted_html}
        </div>
    """, unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.info("""
**Note :** Les données ne sont pas stockées. 
L'extraction dépend de la qualité du modèle choisi.
""")
