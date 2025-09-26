"""
Tests for narrative quality service functionality.
"""

import pytest

from app.services.narrative_quality_service import (
    NarrativeQualityService,
    QualityLevel,
    QualityMetrics
)


class TestNarrativeQualityService:
    """Test cases for the narrative quality service."""

    @pytest.fixture
    def service(self):
        """Create quality service instance."""
        return NarrativeQualityService()

    @pytest.fixture
    def good_narrative(self):
        """Sample good quality narrative."""
        return """John Smith is a 21-year-old shortstop in the Yankees system currently at Double-A.
        His exceptional hitting ability stands out as his premier tool and drives much of his upside.
        Supporting this is solid plate discipline, adding depth to his offensive profile.
        The model projects 75.0% success probability with medium risk, expecting arrival within 2 years with 85.0% confidence."""

    @pytest.fixture
    def poor_narrative(self):
        """Sample poor quality narrative."""
        return "player good maybe"

    @pytest.fixture
    def long_narrative(self):
        """Sample overly long narrative."""
        return """This player is really really good and has many many tools that make him special and unique in ways that are hard to describe but very important.
        He plays baseball very well and his skills are impressive to scouts who watch him play every single day and night.
        The statistics show that he performs at a high level consistently over time and this makes him valuable.
        Many people think he will be successful in the major leagues because of his talent and work ethic.
        His future looks bright and promising for the organization that drafted him."""

    def test_split_sentences(self, service):
        """Test sentence splitting functionality."""
        text = "This is first. This is second! Is this third? Yes."
        sentences = service._split_sentences(text)
        assert len(sentences) == 4
        assert sentences[0] == "This is first"
        assert sentences[1] == "This is second"

    def test_split_words(self, service):
        """Test word splitting functionality."""
        text = "Hello, world! This is a test."
        words = service._split_words(text)
        assert "hello" in words
        assert "world" in words
        assert "test" in words
        assert "," not in words  # Punctuation should be filtered

    def test_estimate_syllables(self, service):
        """Test syllable estimation."""
        assert service._estimate_syllables("cat") == 1
        assert service._estimate_syllables("baseball") == 2
        assert service._estimate_syllables("ability") == 4
        assert service._estimate_syllables("the") == 1

    def test_simple_readability_calculation(self, service):
        """Test simple readability calculation."""
        simple_text = "The cat sat. The dog ran."
        score = service._calculate_simple_readability(simple_text)
        assert 0 <= score <= 100
        assert score > 70  # Should be highly readable

        complex_text = "The multifaceted organizational restructuring paradigm necessitates comprehensive strategic recalibration."
        complex_score = service._calculate_simple_readability(complex_text)
        assert complex_score < score  # Should be less readable

    def test_assess_coherence_good(self, service):
        """Test coherence assessment for good text."""
        sentences = [
            "John is a baseball player",
            "He plays shortstop for the Yankees",
            "His hitting ability is exceptional"
        ]
        score = service._assess_coherence(sentences)
        assert score > 60  # Should have good coherence due to pronouns

    def test_assess_coherence_poor(self, service):
        """Test coherence assessment for poor text."""
        sentences = [
            "Baseball is fun",
            "Pizza is delicious",
            "Cars are fast"
        ]
        score = service._assess_coherence(sentences)
        assert score < 80  # Should have lower coherence

    def test_check_grammar_issues(self, service):
        """Test grammar issue detection."""
        # Good grammar
        good_text = "This is a properly formatted sentence."
        issues = service._check_grammar_issues(good_text)
        assert len(issues) == 0

        # Bad grammar
        bad_text = "this sentence has problems"  # No capital, no period
        issues = service._check_grammar_issues(bad_text)
        assert len(issues) > 0

        # Double spaces
        double_space_text = "This has  double spaces."
        issues = service._check_grammar_issues(double_space_text)
        assert any("spaces" in issue for issue in issues)

    def test_check_content_issues(self, service):
        """Test content issue detection."""
        # Too short
        short_text = "Short."
        sentences = service._split_sentences(short_text)
        words = service._split_words(short_text)
        issues = service._check_content_issues(short_text, sentences, words)
        assert any("few sentences" in issue for issue in issues)
        assert any("few words" in issue for issue in issues)

        # Too long sentence
        long_sentence_text = "This is a very very very very very very very very very very very very very very very very very very very very very very very very very long sentence."
        sentences = service._split_sentences(long_sentence_text)
        words = service._split_words(long_sentence_text)
        issues = service._check_content_issues(long_sentence_text, sentences, words)
        assert any("long sentence" in issue for issue in issues)

    def test_assess_narrative_quality_good(self, service, good_narrative):
        """Test quality assessment for good narrative."""
        metrics = service.assess_narrative_quality(good_narrative)

        assert isinstance(metrics, QualityMetrics)
        assert metrics.sentence_count >= 3
        assert metrics.word_count > 40
        assert metrics.readability_score > 0
        assert metrics.coherence_score > 0
        assert metrics.overall_quality in [QualityLevel.GOOD, QualityLevel.EXCELLENT, QualityLevel.ACCEPTABLE]
        assert metrics.quality_score > 50

    def test_assess_narrative_quality_poor(self, service, poor_narrative):
        """Test quality assessment for poor narrative."""
        metrics = service.assess_narrative_quality(poor_narrative)

        assert metrics.sentence_count < 3
        assert metrics.word_count < 10
        assert metrics.overall_quality == QualityLevel.POOR
        assert metrics.quality_score < 50
        assert len(metrics.content_issues) > 0

    def test_assess_narrative_quality_long(self, service, long_narrative):
        """Test quality assessment for overly long narrative."""
        metrics = service.assess_narrative_quality(long_narrative)

        assert metrics.sentence_count > 4
        assert len(metrics.content_issues) > 0
        assert any("many sentences" in issue for issue in metrics.content_issues)

    def test_calculate_overall_quality(self, service):
        """Test overall quality calculation."""
        # Perfect scores
        score = service._calculate_overall_quality(
            readability_score=80.0,
            sentence_count=4,
            word_count=60,
            avg_sentence_length=15.0,
            coherence_score=80.0,
            grammar_issues=[],
            content_issues=[]
        )
        assert score > 85

        # Poor scores
        score = service._calculate_overall_quality(
            readability_score=30.0,
            sentence_count=1,
            word_count=20,
            avg_sentence_length=40.0,
            coherence_score=30.0,
            grammar_issues=["error1", "error2"],
            content_issues=["issue1", "issue2"]
        )
        assert score < 50

    def test_determine_quality_level(self, service):
        """Test quality level determination."""
        assert service._determine_quality_level(90) == QualityLevel.EXCELLENT
        assert service._determine_quality_level(75) == QualityLevel.GOOD
        assert service._determine_quality_level(60) == QualityLevel.ACCEPTABLE
        assert service._determine_quality_level(40) == QualityLevel.POOR

    def test_validate_narrative_quality_pass(self, service, good_narrative):
        """Test narrative validation for passing narrative."""
        is_valid, metrics = service.validate_narrative_quality(good_narrative, min_quality_score=50.0)

        assert is_valid is True
        assert metrics.overall_quality != QualityLevel.POOR
        assert metrics.quality_score >= 50.0

    def test_validate_narrative_quality_fail(self, service, poor_narrative):
        """Test narrative validation for failing narrative."""
        is_valid, metrics = service.validate_narrative_quality(poor_narrative, min_quality_score=60.0)

        assert is_valid is False
        assert metrics.quality_score < 60.0

    def test_get_quality_feedback(self, service, good_narrative, poor_narrative):
        """Test quality feedback generation."""
        # Good narrative feedback
        good_metrics = service.assess_narrative_quality(good_narrative)
        good_feedback = service.get_quality_feedback(good_metrics)
        assert "Overall quality:" in good_feedback
        assert len(good_feedback) > 20

        # Poor narrative feedback
        poor_metrics = service.assess_narrative_quality(poor_narrative)
        poor_feedback = service.get_quality_feedback(poor_metrics)
        assert "Overall quality:" in poor_feedback
        assert "poor" in poor_feedback.lower()

    def test_quality_metrics_dataclass(self):
        """Test QualityMetrics dataclass functionality."""
        metrics = QualityMetrics(
            readability_score=75.0,
            sentence_count=4,
            word_count=50,
            avg_sentence_length=12.5,
            coherence_score=80.0,
            grammar_issues=[],
            content_issues=[],
            overall_quality=QualityLevel.GOOD,
            quality_score=85.0
        )

        assert metrics.readability_score == 75.0
        assert metrics.overall_quality == QualityLevel.GOOD
        assert len(metrics.grammar_issues) == 0

    def test_edge_cases(self, service):
        """Test edge cases and error handling."""
        # Empty text
        metrics = service.assess_narrative_quality("")
        assert metrics.overall_quality == QualityLevel.POOR
        assert metrics.quality_score == 0.0

        # Single word
        metrics = service.assess_narrative_quality("Baseball.")
        assert metrics.sentence_count == 1
        assert metrics.word_count == 1

        # Very long text
        very_long = "This is a sentence. " * 50
        metrics = service.assess_narrative_quality(very_long)
        assert metrics.word_count > 100
        assert any("many words" in issue for issue in metrics.content_issues)


class TestQualityServiceIntegration:
    """Integration tests for quality service."""

    @pytest.fixture
    def service(self):
        """Service instance for integration tests."""
        return NarrativeQualityService()

    def test_realistic_narrative_assessment(self, service):
        """Test assessment of realistic prospect narrative."""
        narrative = """Marcus Thompson, 20, has advanced quickly through the Dodgers system and currently plays at High-A.
        His proven power potential has been the catalyst for his rapid ascension and drives significant upside.
        Additionally, his plate discipline adds another dimension to his offensive profile.
        The model projects 72% success probability with medium risk, expecting arrival within 3 years with 80% confidence."""

        metrics = service.assess_narrative_quality(narrative)

        # Should be good quality
        assert metrics.overall_quality in [QualityLevel.GOOD, QualityLevel.EXCELLENT]
        assert metrics.sentence_count == 4  # Perfect target
        assert 50 <= metrics.word_count <= 80  # Reasonable range
        assert metrics.readability_score > 40  # Readable
        assert metrics.coherence_score > 60  # Good flow
        assert len(metrics.grammar_issues) <= 1  # Minimal grammar issues

    def test_quality_improvement_workflow(self, service):
        """Test workflow for improving narrative quality."""
        # Start with poor narrative
        poor_narrative = "player good fast maybe success"

        # Assess initial quality
        initial_metrics = service.assess_narrative_quality(poor_narrative)
        assert initial_metrics.overall_quality == QualityLevel.POOR

        # Improved narrative
        improved_narrative = """This player shows promising development as a young prospect.
        His speed and athleticism are his standout tools that drive his potential.
        With continued development, he could contribute in the future.
        The projection model shows moderate success probability with his current trajectory."""

        # Assess improved quality
        improved_metrics = service.assess_narrative_quality(improved_narrative)
        assert improved_metrics.quality_score > initial_metrics.quality_score
        assert improved_metrics.overall_quality != QualityLevel.POOR

    def test_different_narrative_styles(self, service):
        """Test quality assessment across different narrative styles."""
        # Power hitter narrative
        power_narrative = """Jake Martinez brings tremendous raw power as a 22-year-old first baseman.
        His exit velocity and home run potential serve as his primary tools for advancement.
        Questions about contact ability create some uncertainty in his development path.
        The model assigns 65% success probability with high risk given his swing-and-miss tendencies."""

        # Contact hitter narrative
        contact_narrative = """Sarah Johnson profiles as a contact-first middle infielder at 21 years old.
        Her exceptional plate discipline and bat-to-ball skills form the foundation of her value.
        Limited power potential caps her overall ceiling but provides a solid floor.
        The projection shows 70% success probability with low risk due to her advanced approach."""

        power_metrics = service.assess_narrative_quality(power_narrative)
        contact_metrics = service.assess_narrative_quality(contact_narrative)

        # Both should be reasonable quality
        assert power_metrics.overall_quality != QualityLevel.POOR
        assert contact_metrics.overall_quality != QualityLevel.POOR

        # Both should have good structure
        assert power_metrics.sentence_count == 4
        assert contact_metrics.sentence_count == 4