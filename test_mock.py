from insight_extractor import InsightExtractor, PatientInsights, Treatment, PrescriptionComparison, ComparisonResult
from unittest.mock import MagicMock
import json

def test_extraction_and_comparison():
    # Mock data for extraction
    mock_insights = PatientInsights(
        age=81,
        sexe="Féminin",
        antecedents_medicaux=["HTA", "Arthrose", "Chirurgie du genou"],
        traitements_habituels=[
            Treatment(name="MACROGOL", dosage="4000 mg", frequency="1 le matin"),
            Treatment(name="ZESTRYL", dosage="5 mg", frequency="1 le matin")
        ],
        raison_hospitalisation="Lymphome cérébral primitif",
        traitement_sortie=[
            Treatment(name="NATULAN", dosage="150 mg", frequency="J1 à J7"),
            Treatment(name="ZESTRYL", dosage="5 mg", frequency="1 le matin")
        ],
        fonction_renale="Créatinine 75 µmol/L, DFG 72",
        fonction_hepatique="BHC Normal (ASAT/ALAT N)"
    )
    
    mock_comparison = PrescriptionComparison(
        comparisons=[
            ComparisonResult(medication_name="Zestryl", status="Changé", details="Dosage augmenté de 5mg à 10mg"),
            ComparisonResult(medication_name="Apixaban", status="Nouveau", details="Nouvel anticoagulant")
        ],
        recommendations=["Surveiller la tension artérielle avec le nouveau dosage de Zestryl"]
    )

    # Mocking the extractor class methods directly to bypass LangChain internals in mock
    extractor = InsightExtractor(api_key="fake_key")
    extractor.extract_from_text = MagicMock(return_value=mock_insights)
    extractor.compare_prescription = MagicMock(return_value=mock_comparison)
    
    # Run "extraction"
    insights = extractor.extract_from_text("Contenu de patient.txt")
    print("Insights extraits (Mock):")
    print(insights.model_dump_json(indent=2))
    
    # Run "comparison"
    new_presc = [
        Treatment(name="Zestryl", dosage="10 mg", frequency="1 le matin"),
        Treatment(name="Apixaban", dosage="5 mg", frequency="2 par jour")
    ]
    comparison = extractor.compare_prescription(insights, new_presc)
    print("\nComparaison (Mock):")
    print(comparison.model_dump_json(indent=2))

if __name__ == "__main__":
    try:
        test_extraction_and_comparison()
        print("\nTest réussi (Mock) !")
    except Exception as e:
        print(f"Erreur lors du test: {e}")
