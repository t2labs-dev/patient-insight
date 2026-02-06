from insight_extractor import InsightExtractor, Treatment
import os
import sys

def main():
    # Initialisation de l'extracteur
    # Vous pouvez changer le provider en 'ollama' pour un modèle local
    model_provider = os.getenv("MODEL_PROVIDER", "openai")
    model_name = os.getenv("MODEL_NAME", "gpt-4o")
    
    print(f"Utilisation du provider: {model_provider}, modèle: {model_name}")
    
    extractor = InsightExtractor(
        model_provider=model_provider,
        model_name=model_name
    )

    # Lecture du fichier patient
    patient_file = "patient.txt"
    if not os.path.exists(patient_file):
        print(f"Erreur: Le fichier {patient_file} est introuvable.")
        return

    with open(patient_file, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"--- Extraction des insights depuis {patient_file} ---")
    try:
        insights = extractor.extract_from_text(content)
        print("\n[Insights Extraits]")
        print(insights.model_dump_json(indent=2))
        
        # Exemple de nouvelle prescription médicale pour comparaison
        print("\n--- Comparaison avec une nouvelle prescription ---")
        new_prescription = [
            Treatment(name="Zestryl", dosage="10 mg", frequency="1 comprimé le matin"),
            Treatment(name="Doliprane", dosage="1 g", frequency="3 fois par jour si douleurs"),
            Treatment(name="Eliquis", dosage="5 mg", frequency="1 matin et soir")
        ]
        
        comparison = extractor.compare_prescription(insights, new_prescription)
        print("\n[Résultat de la Comparaison]")
        print(comparison.model_dump_json(indent=2))

    except Exception as e:
        print(f"Une erreur est survenue lors de l'appel à l'IA : {e}")
        if model_provider == "openai":
            print("Note: Assurez-vous que votre clé API OpenAI est correcte.")
        elif model_provider == "ollama":
            print("Note: Assurez-vous qu'Ollama est lancé et que le modèle est téléchargé (ex: ollama run mistral).")
        elif model_provider == "mistral":
            print("Note: Assurez-vous que votre clé API Mistral est correcte.")

if __name__ == "__main__":
    main()
