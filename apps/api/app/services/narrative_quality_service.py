"""
Narrative Quality Assurance Service for AI Player Outlook Generation

This service provides readability scoring, coherence validation, and content
quality metrics for generated prospect narratives.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    import textstat
except ImportError:
    textstat = None

logger = logging.getLogger(__name__)


class QualityLevel(str, Enum):
    """Quality assessment levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"


@dataclass
class QualityMetrics:
    """Container for narrative quality metrics."""
    readability_score: float
    sentence_count: int
    word_count: int
    avg_sentence_length: float
    coherence_score: float
    grammar_issues: List[str]
    content_issues: List[str]
    overall_quality: QualityLevel
    quality_score: float  # 0-100 scale


class NarrativeQualityService:
    """
    Service for assessing and ensuring quality of generated prospect narratives.
    """

    def __init__(self):
        """Initialize the narrative quality service."""
        self.min_readability_score = 60.0  # Flesch Reading Ease
        self.target_sentence_count = (3, 4)  # 3-4 sentences
        self.max_sentence_length = 25  # words per sentence
        self.min_word_count = 40
        self.max_word_count = 100

    def assess_narrative_quality(self, narrative: str) -> QualityMetrics:
        """
        Comprehensive quality assessment of a narrative.

        Args:
            narrative: Generated narrative text

        Returns:
            QualityMetrics object with detailed assessment
        """
        try:
            # Basic text analysis
            sentences = self._split_sentences(narrative)
            words = self._split_words(narrative)

            sentence_count = len(sentences)
            word_count = len(words)
            avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0

            # Readability assessment
            readability_score = self._calculate_readability(narrative)

            # Coherence assessment
            coherence_score = self._assess_coherence(sentences)

            # Grammar and content validation
            grammar_issues = self._check_grammar_issues(narrative)
            content_issues = self._check_content_issues(narrative, sentences, words)

            # Calculate overall quality
            quality_score = self._calculate_overall_quality(
                readability_score=readability_score,
                sentence_count=sentence_count,
                word_count=word_count,
                avg_sentence_length=avg_sentence_length,
                coherence_score=coherence_score,
                grammar_issues=grammar_issues,
                content_issues=content_issues
            )

            overall_quality = self._determine_quality_level(quality_score)

            return QualityMetrics(
                readability_score=readability_score,
                sentence_count=sentence_count,
                word_count=word_count,
                avg_sentence_length=avg_sentence_length,
                coherence_score=coherence_score,
                grammar_issues=grammar_issues,
                content_issues=content_issues,
                overall_quality=overall_quality,
                quality_score=quality_score
            )

        except Exception as e:
            logger.error(f"Failed to assess narrative quality: {e}")
            # Return minimal metrics on error
            return QualityMetrics(
                readability_score=0.0,
                sentence_count=0,
                word_count=0,
                avg_sentence_length=0.0,
                coherence_score=0.0,
                grammar_issues=["Assessment failed"],
                content_issues=["Assessment failed"],
                overall_quality=QualityLevel.POOR,
                quality_score=0.0
            )

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting on periods, exclamation marks, question marks
        sentences = re.split(r'[.!?]+', text)
        # Clean and filter empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences

    def _split_words(self, text: str) -> List[str]:
        """Split text into words."""
        # Split on whitespace and punctuation, keep only words
        words = re.findall(r'\b\w+\b', text.lower())
        return words

    def _calculate_readability(self, text: str) -> float:
        """
        Calculate Flesch Reading Ease score.

        Args:
            text: Text to analyze

        Returns:
            Readability score (0-100, higher is more readable)
        """
        try:
            if textstat:
                # Use textstat library if available
                score = textstat.flesch_reading_ease(text)
                return max(0.0, min(100.0, score))
            else:
                # Fallback calculation
                return self._calculate_simple_readability(text)

        except Exception as e:
            logger.warning(f"Readability calculation failed: {e}")
            return self._calculate_simple_readability(text)

    def _calculate_simple_readability(self, text: str) -> float:
        """
        Simple readability calculation without external dependencies.

        Based on average sentence length and syllable estimation.
        """
        sentences = self._split_sentences(text)
        words = self._split_words(text)

        if not sentences or not words:
            return 0.0

        avg_sentence_length = len(words) / len(sentences)
        avg_syllables = sum(self._estimate_syllables(word) for word in words) / len(words)

        # Simplified Flesch formula approximation
        score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables)
        return max(0.0, min(100.0, score))

    def _estimate_syllables(self, word: str) -> int:
        """Estimate syllable count for a word."""
        word = word.lower()
        vowels = 'aeiouy'
        syllable_count = 0
        prev_was_vowel = False

        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_was_vowel:
                syllable_count += 1
            prev_was_vowel = is_vowel

        # Adjust for silent 'e'
        if word.endswith('e') and syllable_count > 1:
            syllable_count -= 1

        return max(1, syllable_count)

    def _assess_coherence(self, sentences: List[str]) -> float:
        """
        Assess narrative coherence based on sentence flow and transitions.

        Args:
            sentences: List of sentences

        Returns:
            Coherence score (0-100)
        """
        if len(sentences) < 2:
            return 100.0  # Single sentence is coherent by default

        coherence_score = 100.0

        # Check for transition words/phrases
        transition_words = {
            'however', 'therefore', 'additionally', 'furthermore', 'meanwhile',
            'consequently', 'nevertheless', 'moreover', 'thus', 'hence',
            'while', 'although', 'because', 'since', 'despite', 'given',
            'his', 'her', 'their', 'this', 'that', 'these', 'those'
        }

        # Check pronoun usage (good for coherence)
        pronouns = {'he', 'his', 'him', 'she', 'her', 'they', 'their', 'them', 'it', 'its'}

        transition_count = 0
        pronoun_count = 0

        for sentence in sentences[1:]:  # Skip first sentence
            words = self._split_words(sentence)
            sentence_words = set(words)

            # Count transitions and pronouns
            if sentence_words & transition_words:
                transition_count += 1
            if sentence_words & pronouns:
                pronoun_count += 1

        # Calculate coherence based on transitions and pronouns
        if len(sentences) > 1:
            transition_ratio = transition_count / (len(sentences) - 1)
            pronoun_ratio = pronoun_count / (len(sentences) - 1)

            # Good coherence has some transitions and pronouns
            coherence_score = min(100.0, 60.0 + (transition_ratio * 20) + (pronoun_ratio * 20))

        return coherence_score

    def _check_grammar_issues(self, text: str) -> List[str]:
        """
        Check for basic grammar issues.

        Args:
            text: Text to check

        Returns:
            List of grammar issues found
        """
        issues = []

        # Check for basic capitalization
        sentences = self._split_sentences(text)
        for sentence in sentences:
            if sentence and not sentence[0].isupper():
                issues.append("Sentence does not start with capital letter")
                break

        # Check for proper sentence endings
        if text and text[-1] not in '.!?':
            issues.append("Text does not end with proper punctuation")

        # Check for double spaces
        if '  ' in text:
            issues.append("Contains multiple consecutive spaces")

        # Check for common grammar patterns
        if re.search(r'\ba\s+[aeiouAEIOU]', text):
            issues.append("Possible article usage error (a + vowel)")

        # Check for sentence fragments (very basic)
        for sentence in sentences:
            words = self._split_words(sentence)
            if len(words) < 3:
                issues.append("Very short sentence detected (possible fragment)")
                break

        return issues

    def _check_content_issues(
        self,
        text: str,
        sentences: List[str],
        words: List[str]
    ) -> List[str]:
        """
        Check for content-specific issues.

        Args:
            text: Full text
            sentences: List of sentences
            words: List of words

        Returns:
            List of content issues found
        """
        issues = []

        # Check sentence count
        if len(sentences) < self.target_sentence_count[0]:
            issues.append(f"Too few sentences ({len(sentences)} < {self.target_sentence_count[0]})")
        elif len(sentences) > self.target_sentence_count[1]:
            issues.append(f"Too many sentences ({len(sentences)} > {self.target_sentence_count[1]})")

        # Check word count
        if len(words) < self.min_word_count:
            issues.append(f"Too few words ({len(words)} < {self.min_word_count})")
        elif len(words) > self.max_word_count:
            issues.append(f"Too many words ({len(words)} > {self.max_word_count})")

        # Check for very long sentences
        for sentence in sentences:
            sentence_words = self._split_words(sentence)
            if len(sentence_words) > self.max_sentence_length:
                issues.append(f"Very long sentence detected ({len(sentence_words)} words)")
                break

        # Check for repetitive content
        word_freq = {}
        for word in words:
            if len(word) > 4:  # Only check longer words
                word_freq[word] = word_freq.get(word, 0) + 1

        repeated_words = [word for word, count in word_freq.items() if count > 2]
        if repeated_words:
            issues.append(f"Repetitive words detected: {', '.join(repeated_words[:3])}")

        # Check for missing prospect information
        if not any(word.istitle() for word in words):
            issues.append("No proper nouns detected (possible missing prospect name)")

        return issues

    def _calculate_overall_quality(
        self,
        readability_score: float,
        sentence_count: int,
        word_count: int,
        avg_sentence_length: float,
        coherence_score: float,
        grammar_issues: List[str],
        content_issues: List[str]
    ) -> float:
        """
        Calculate overall quality score (0-100).

        Args:
            Various quality metrics

        Returns:
            Overall quality score
        """
        score = 0.0

        # Readability component (30%)
        if readability_score >= self.min_readability_score:
            readability_component = 30.0
        else:
            readability_component = 30.0 * (readability_score / self.min_readability_score)

        # Structure component (25%)
        structure_component = 25.0
        if sentence_count < self.target_sentence_count[0] or sentence_count > self.target_sentence_count[1]:
            structure_component *= 0.7
        if word_count < self.min_word_count or word_count > self.max_word_count:
            structure_component *= 0.8
        if avg_sentence_length > self.max_sentence_length:
            structure_component *= 0.8

        # Coherence component (25%)
        coherence_component = 25.0 * (coherence_score / 100.0)

        # Grammar component (10%)
        grammar_component = 10.0
        if grammar_issues:
            grammar_component *= max(0.2, 1.0 - (len(grammar_issues) * 0.2))

        # Content component (10%)
        content_component = 10.0
        if content_issues:
            content_component *= max(0.2, 1.0 - (len(content_issues) * 0.15))

        score = (
            readability_component +
            structure_component +
            coherence_component +
            grammar_component +
            content_component
        )

        return max(0.0, min(100.0, score))

    def _determine_quality_level(self, quality_score: float) -> QualityLevel:
        """Determine quality level from numeric score."""
        if quality_score >= 85:
            return QualityLevel.EXCELLENT
        elif quality_score >= 70:
            return QualityLevel.GOOD
        elif quality_score >= 55:
            return QualityLevel.ACCEPTABLE
        else:
            return QualityLevel.POOR

    def validate_narrative_quality(
        self,
        narrative: str,
        min_quality_score: float = 60.0
    ) -> Tuple[bool, QualityMetrics]:
        """
        Validate if narrative meets minimum quality standards.

        Args:
            narrative: Generated narrative
            min_quality_score: Minimum acceptable quality score

        Returns:
            Tuple of (is_valid, quality_metrics)
        """
        metrics = self.assess_narrative_quality(narrative)
        is_valid = (
            metrics.quality_score >= min_quality_score and
            metrics.overall_quality != QualityLevel.POOR
        )
        return is_valid, metrics

    def get_quality_feedback(self, metrics: QualityMetrics) -> str:
        """
        Generate human-readable quality feedback.

        Args:
            metrics: Quality metrics

        Returns:
            Feedback string
        """
        feedback_parts = []

        # Overall assessment
        feedback_parts.append(f"Overall quality: {metrics.overall_quality.value} ({metrics.quality_score:.1f}/100)")

        # Specific feedback
        if metrics.readability_score < self.min_readability_score:
            feedback_parts.append(f"Readability could be improved (score: {metrics.readability_score:.1f})")

        if metrics.sentence_count < self.target_sentence_count[0]:
            feedback_parts.append("Consider adding more detail (too few sentences)")
        elif metrics.sentence_count > self.target_sentence_count[1]:
            feedback_parts.append("Consider condensing content (too many sentences)")

        if metrics.avg_sentence_length > self.max_sentence_length:
            feedback_parts.append("Consider breaking up long sentences")

        if metrics.coherence_score < 70:
            feedback_parts.append("Improve sentence flow and transitions")

        if metrics.grammar_issues:
            feedback_parts.append(f"Grammar issues: {'; '.join(metrics.grammar_issues[:2])}")

        if metrics.content_issues:
            feedback_parts.append(f"Content issues: {'; '.join(metrics.content_issues[:2])}")

        return ". ".join(feedback_parts) + "."


# Singleton instance for application use
narrative_quality_service = NarrativeQualityService()