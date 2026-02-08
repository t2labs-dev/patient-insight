"""
Tests for Patient Insight Extractor

These are mock tests that validate the data models and basic functionality
without requiring actual LLM API calls.
"""

import pytest
from unittest.mock import MagicMock, patch
from insight_extractor import (
    InsightExtractor,
    PatientInsights,
    Treatment,
    PrescriptionComparison,
    ComparisonResult,
    Sexe
)


@pytest.fixture
def mock_patient_insights():
    """Fixture providing sample patient insights data"""
    return PatientInsights(
        age=81,
        sexe=Sexe.FEMININ,
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


@pytest.fixture
def mock_prescription_comparison():
    """Fixture providing sample prescription comparison data"""
    return PrescriptionComparison(
        comparisons=[
            ComparisonResult(
                medication_name="Zestryl",
                status="Changé",
                details="Dosage augmenté de 5mg à 10mg"
            ),
            ComparisonResult(
                medication_name="Apixaban",
                status="Nouveau",
                details="Nouvel anticoagulant"
            )
        ],
        recommendations=["Surveiller la tension artérielle avec le nouveau dosage de Zestryl"]
    )


def test_treatment_model():
    """Test Treatment data model"""
    treatment = Treatment(
        name="DOLIPRANE",
        dosage="1000 mg",
        frequency="3 fois par jour"
    )

    assert treatment.name == "DOLIPRANE"
    assert treatment.dosage == "1000 mg"
    assert treatment.frequency == "3 fois par jour"


def test_patient_insights_model(mock_patient_insights):
    """Test PatientInsights data model"""
    insights = mock_patient_insights

    assert insights.age == 81
    assert insights.sexe == Sexe.FEMININ
    assert len(insights.antecedents_medicaux) == 3
    assert "HTA" in insights.antecedents_medicaux
    assert len(insights.traitements_habituels) == 2
    assert insights.traitements_habituels[0].name == "MACROGOL"
    assert insights.raison_hospitalisation == "Lymphome cérébral primitif"
    assert "Créatinine" in insights.fonction_renale


def test_prescription_comparison_model(mock_prescription_comparison):
    """Test PrescriptionComparison data model"""
    comparison = mock_prescription_comparison

    assert len(comparison.comparisons) == 2
    assert comparison.comparisons[0].medication_name == "Zestryl"
    assert comparison.comparisons[0].status == "Changé"
    assert comparison.comparisons[1].medication_name == "Apixaban"
    assert comparison.comparisons[1].status == "Nouveau"
    assert len(comparison.recommendations) == 1
    assert "Surveiller" in comparison.recommendations[0]


@patch.dict('os.environ', {'OPENAI_API_KEY': 'fake-test-key'}, clear=False)
def test_extractor_initialization():
    """Test InsightExtractor initialization with mocked environment"""
    extractor = InsightExtractor(model_provider="openai", api_key="fake_key")

    assert extractor is not None
    assert extractor.llm is not None


def test_extraction_with_mock(mock_patient_insights):
    """Test extraction flow with mocked LLM response"""
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'fake-test-key'}, clear=False):
        extractor = InsightExtractor(model_provider="openai", api_key="fake_key")
        extractor.extract_from_text = MagicMock(return_value=mock_patient_insights)

        # Test extraction
        insights = extractor.extract_from_text("Contenu de patient.txt")

        # Assertions
        assert insights is not None
        assert isinstance(insights, PatientInsights)
        assert insights.age == 81
        assert len(insights.traitements_habituels) == 2

        # Verify the mock was called
        extractor.extract_from_text.assert_called_once_with("Contenu de patient.txt")


def test_comparison_with_mock(mock_patient_insights, mock_prescription_comparison):
    """Test prescription comparison flow with mocked LLM response"""
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'fake-test-key'}, clear=False):
        extractor = InsightExtractor(model_provider="openai", api_key="fake_key")
        extractor.compare_prescription = MagicMock(return_value=mock_prescription_comparison)

        # New prescription
        new_prescription = [
            Treatment(name="Zestryl", dosage="10 mg", frequency="1 le matin"),
            Treatment(name="Apixaban", dosage="5 mg", frequency="2 par jour")
        ]

        # Test comparison
        comparison = extractor.compare_prescription(mock_patient_insights, new_prescription)

        # Assertions
        assert comparison is not None
        assert isinstance(comparison, PrescriptionComparison)
        assert len(comparison.comparisons) == 2
        assert comparison.comparisons[0].medication_name == "Zestryl"
        assert comparison.comparisons[0].status == "Changé"
        assert len(comparison.recommendations) >= 1

        # Verify the mock was called
        extractor.compare_prescription.assert_called_once()


def test_json_serialization(mock_patient_insights):
    """Test that models can be serialized to JSON"""
    insights_json = mock_patient_insights.model_dump_json()

    assert insights_json is not None
    assert isinstance(insights_json, str)
    assert "Lymphome cérébral primitif" in insights_json
    assert "MACROGOL" in insights_json


def test_treatment_without_frequency():
    """Test Treatment model with optional frequency"""
    treatment = Treatment(
        name="ASPIRIN",
        dosage="100 mg",
        frequency=None
    )

    assert treatment.name == "ASPIRIN"
    assert treatment.dosage == "100 mg"
    assert treatment.frequency is None
