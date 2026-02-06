import warnings
import os
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI

# Ignorer l'avertissement de dépréciation de Pydantic V1 sur Python 3.14+
warnings.filterwarnings("ignore", category=UserWarning, message=".*Pydantic V1.*")

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List, Optional, Union

load_dotenv()

class Treatment(BaseModel):
    name: str = Field(..., description="Nom du médicament")
    dosage: str = Field(..., description="Posologie/Dosage")
    frequency: Optional[str] = Field(None, description="Fréquence de prise")

class PatientInsights(BaseModel):
    age: Optional[int] = Field(None, description="Âge du patient")
    sexe: Optional[str] = Field(None, description="Sexe du patient")
    antecedents_medicaux: List[str] = Field(..., description="Antécédents médicaux du patient")
    traitements_habituels: List[Treatment] = Field(..., description="Liste des traitements habituels")
    raison_hospitalisation: str = Field(..., description="Pourquoi le patient est hospitalisé")
    traitement_sortie: List[Treatment] = Field(..., description="Traitements prévus à la sortie")
    fonction_renale: str = Field(..., description="Informations sur la fonction rénale (ex: Clairance, créatinine)")
    fonction_hepatique: str = Field(..., description="Informations sur la fonction hépatique (ex: BHC, ASAT/ALAT)")

class ComparisonResult(BaseModel):
    medication_name: str
    status: str = Field(..., description="Status: 'Nouveau', 'Changé', 'Identique', 'Arrêté'")
    details: Optional[str] = Field(None, description="Détails sur le changement ou l'observation")

class PrescriptionComparison(BaseModel):
    comparisons: List[ComparisonResult]
    recommendations: List[str]

class InsightExtractor:
    def __init__(self, model_provider: str = "openai", model_name: Optional[str] = None, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize the extractor with a specific provider and model.
        :param model_provider: 'openai' or 'ollama' (for local)
        :param model_name: Name of the model (e.g. 'gpt-4o', 'llama3')
        :param api_key: API key for OpenAI
        :param base_url: Base URL for local models or proxy
        """
        if model_provider == "openai":
            self.llm = ChatOpenAI(
                model=model_name or "gpt-4o",
                api_key=api_key or os.getenv("OPENAI_API_KEY"),
                base_url=base_url
            )
        elif model_provider == "ollama":
            self.llm = ChatOllama(
                model=model_name or "llama3",
                base_url=base_url or "http://localhost:11434"
            )
        elif model_provider == "mistral":
            self.llm = ChatMistralAI(model=model_name or "mistral-small-latest")
        else:
            raise ValueError(f"Provider {model_provider} non supporté.")

    def extract_from_text(self, text: str) -> PatientInsights:
        try:
            structured_llm = self.llm.with_structured_output(PatientInsights)
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Tu es un assistant médical expert en extraction de données structurées à partir de comptes-rendus d'hospitalisation en français. "
                           "Les listes de traitements doivent être ordonnées par ordre alphabétique (insensible à la casse) et le nom des médicaments doit être en MAJUSCULES."),
                ("user", "Extrait les informations structurées du texte suivant :\n\n{text}")
            ])
            chain = prompt | structured_llm
            return chain.invoke({"text": text})
        except (NotImplementedError, AttributeError, Exception) as e:
            # Fallback pour les modèles ne supportant pas with_structured_output (ex: Ollama mistral)
            parser = PydanticOutputParser(pydantic_object=PatientInsights)
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Tu es un assistant médical expert en extraction de données structurées à partir de comptes-rendus d'hospitalisation en français.\n"
                           "Les listes de traitements doivent être ordonnées par ordre alphabétique (insensible à la casse) et le nom des médicaments doit être en MAJUSCULES.\n"
                           "{format_instructions}"),
                ("user", "Extrait les informations structurées du texte suivant :\n\n{text}")
            ])
            chain = prompt | self.llm | parser
            return chain.invoke({
                "text": text,
                "format_instructions": parser.get_format_instructions()
            })

    def compare_prescription(self, insights: PatientInsights, new_prescription: List[Treatment]) -> PrescriptionComparison:
        existing_treatments_str = "\n".join([f"- {t.name} {t.dosage} {t.frequency}" for t in insights.traitements_habituels])
        new_prescription_str = "\n".join([f"- {t.name} {t.dosage} {t.frequency}" for t in new_prescription])

        try:
            structured_llm = self.llm.with_structured_output(PrescriptionComparison)
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Tu es un expert en pharmacologie. Compare la nouvelle prescription avec les traitements habituels du patient."),
                ("user", "Traitements habituels :\n{existing_treatments}\n\nNouvelle prescription :\n{new_prescription}\n\nAnalyse les différences (nouveaux, arrêtés, modifiés) et donne des recommandations si nécessaire.")
            ])
            chain = prompt | structured_llm
            return chain.invoke({
                "existing_treatments": existing_treatments_str,
                "new_prescription": new_prescription_str
            })
        except (NotImplementedError, AttributeError, Exception):
            # Fallback
            parser = PydanticOutputParser(pydantic_object=PrescriptionComparison)
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Tu es un expert en pharmacologie. Compare la nouvelle prescription avec les traitements habituels du patient.\n{format_instructions}"),
                ("user", "Traitements habituels :\n{existing_treatments}\n\nNouvelle prescription :\n{new_prescription}\n\nAnalyse les différences (nouveaux, arrêtés, modifiés) et donne des recommandations si nécessaire.")
            ])
            chain = prompt | self.llm | parser
            return chain.invoke({
                "existing_treatments": existing_treatments_str,
                "new_prescription": new_prescription_str,
                "format_instructions": parser.get_format_instructions()
            })

if __name__ == "__main__":
    # Example usage (will require OPENAI_API_KEY in environment)
    extractor = InsightExtractor()
    
    with open("patient.txt", "r") as f:
        content = f.read()
        
    insights = extractor.extract_from_text(content)
    print("--- INSIGHTS EXTRAITS ---")
    print(insights.model_dump_json(indent=2))
    
    # Example new prescription
    new_presc = [
        Treatment(name="Zestryl", dosage="10 mg", frequency="1 comprimé le matin"), # Dosage increased from 5mg
        Treatment(name="Paracetamol", dosage="1 g", frequency="si besoin"),
        Treatment(name="Apixaban", dosage="5 mg", frequency="2 fois par jour") # New
    ]
    
    comparison = extractor.compare_prescription(insights, new_presc)
    print("\n--- COMPARAISON DE PRESCRIPTION ---")
    print(comparison.model_dump_json(indent=2))
