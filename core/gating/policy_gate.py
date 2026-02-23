"""
PolicyGate - Sistema di gating per validazione contenuti.

Allineato con Framework NoNoise v2.
Implementa il Control Layer con constraint checking e semantic validation.

Flags:
- GREEN: contenuto OK, procedi
- YELLOW: warning, rivedi manualmente
- RED: contenuto bloccato, non procedere

Example:
    >>> gate = PolicyGate()
    >>> result = gate.check(output)
    >>> if result.flag == PolicyFlag.RED:
    ...     print(f"Blocked: {result.violations}")
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
import re


class PolicyFlag(Enum):
    """Flag di policy per decisioni gating."""
    GREEN = "green"    # OK, procedi
    YELLOW = "yellow"  # Warning, richiede review
    RED = "red"        # Bloccato, non procedere


@dataclass
class PolicyViolation:
    """Singola violazione di policy."""
    rule_id: str
    rule_name: str
    severity: PolicyFlag
    message: str
    context: Optional[str] = None  # Testo che ha causato violazione

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "message": self.message,
            "context": self.context
        }


@dataclass
class PolicyResult:
    """Risultato di una valutazione policy."""
    flag: PolicyFlag
    violations: List[PolicyViolation] = field(default_factory=list)
    warnings: List[PolicyViolation] = field(default_factory=list)
    passed_rules: List[str] = field(default_factory=list)

    @property
    def is_ok(self) -> bool:
        """True se nessuna violazione RED."""
        return self.flag != PolicyFlag.RED

    @property
    def has_warnings(self) -> bool:
        """True se ci sono warning YELLOW."""
        return self.flag == PolicyFlag.YELLOW or len(self.warnings) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flag": self.flag.value,
            "is_ok": self.is_ok,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": [w.to_dict() for w in self.warnings],
            "passed_rules": self.passed_rules,
            "summary": self._summary()
        }

    def _summary(self) -> str:
        """Riassunto leggibile."""
        if self.flag == PolicyFlag.GREEN:
            return f"All {len(self.passed_rules)} checks passed"
        elif self.flag == PolicyFlag.YELLOW:
            return f"{len(self.warnings)} warnings, {len(self.passed_rules)} passed"
        else:
            return f"{len(self.violations)} violations, {len(self.warnings)} warnings"


class PolicyGate:
    """
    Sistema di gating per validazione contenuti.

    Applica regole di constraint checking e semantic validation
    agli output del Director.

    Rules Categories:
    - Content Safety: no inappropriate content
    - Brand Compliance: marine-only, no logos
    - Structure Validation: correct format
    - Archetype Consistency: matches profile
    """

    # Blacklist terms (RED flags)
    BLACKLIST_TERMS: Set[str] = {
        # Urban/non-marine
        "city", "urban", "building", "skyscraper", "street", "road",
        "car", "traffic", "apartment", "office",
        # Violence/danger
        "blood", "death", "violence", "weapon", "gun", "knife",
        "explosion", "crash", "accident", "disaster",
        # Inappropriate
        "nude", "naked", "explicit", "sexual",
        # Non-marine nature
        "forest", "mountain", "desert", "jungle", "snow", "ice"
    }

    # Warning terms (YELLOW flags)
    WARNING_TERMS: Set[str] = {
        # Potentially problematic
        "storm", "lightning", "danger", "dark", "fear",
        # Needs review
        "person", "human", "face", "crowd", "people",
        # Brand risk
        "logo", "brand", "text", "sign", "advertisement"
    }

    # Required marine vocabulary (at least some should appear)
    MARINE_VOCABULARY: Set[str] = {
        "sea", "ocean", "wave", "water", "shore", "coast", "beach",
        "horizon", "tide", "marine", "nautical", "boat", "yacht",
        "sunset", "sunrise", "sky", "cloud", "reflection", "blue",
        "calm", "ripple", "foam", "spray", "salt", "breeze", "wind"
    }

    # Archetype keywords for consistency check
    ARCHETYPE_KEYWORDS: Dict[str, Set[str]] = {
        "sage": {
            "contemplative", "minimal", "serene", "philosophical", "timeless",
            "still", "calm", "quiet", "peaceful", "meditative", "slow",
            "horizon", "vastness", "infinite", "reflection"
        },
        "rebel": {
            "dynamic", "bold", "powerful", "energetic", "dramatic",
            "crashing", "intense", "wild", "freedom", "adventure",
            "speed", "motion", "force", "breaking", "rush"
        },
        "lover": {
            "warm", "intimate", "sensual", "romantic", "gentle",
            "soft", "golden", "tender", "close", "embrace",
            "sunset", "glow", "touch", "delicate", "caress"
        }
    }

    def __init__(self, strict_mode: bool = False):
        """
        Inizializza PolicyGate.

        Args:
            strict_mode: Se True, warning diventano violations
        """
        self.strict_mode = strict_mode

    def check(
        self,
        output: Dict[str, Any],
        profile: Optional[Dict[str, Any]] = None
    ) -> PolicyResult:
        """
        Valuta un output del Director.

        Args:
            output: Output del Director (video_triptych, ost_prompt, metadata)
            profile: Profilo originale (per consistency check)

        Returns:
            PolicyResult con flag e violazioni
        """
        violations: List[PolicyViolation] = []
        warnings: List[PolicyViolation] = []
        passed: List[str] = []

        # Estrai tutti i prompt per analisi
        all_text = self._extract_all_text(output)

        # Rule 1: Blacklist check
        blacklist_result = self._check_blacklist(all_text)
        if blacklist_result:
            violations.extend(blacklist_result)
        else:
            passed.append("R001_blacklist")

        # Rule 2: Warning terms check
        warning_result = self._check_warnings(all_text)
        if warning_result:
            warnings.extend(warning_result)
        else:
            passed.append("R002_warnings")

        # Rule 3: Marine vocabulary presence
        marine_result = self._check_marine_vocabulary(all_text)
        if marine_result:
            warnings.extend(marine_result)
        else:
            passed.append("R003_marine_vocab")

        # Rule 4: Structure validation
        structure_result = self._check_structure(output)
        if structure_result:
            violations.extend(structure_result)
        else:
            passed.append("R004_structure")

        # Rule 5: Scene sequence validation
        sequence_result = self._check_scene_sequence(output)
        if sequence_result:
            violations.extend(sequence_result)
        else:
            passed.append("R005_sequence")

        # Rule 6: Archetype consistency (if profile provided)
        if profile:
            consistency_result = self._check_archetype_consistency(output, profile)
            if consistency_result:
                warnings.extend(consistency_result)
            else:
                passed.append("R006_archetype")

        # Rule 7: Prompt length check
        length_result = self._check_prompt_lengths(output)
        if length_result:
            warnings.extend(length_result)
        else:
            passed.append("R007_length")

        # Determine final flag
        if violations:
            flag = PolicyFlag.RED
        elif warnings:
            flag = PolicyFlag.YELLOW if not self.strict_mode else PolicyFlag.RED
        else:
            flag = PolicyFlag.GREEN

        return PolicyResult(
            flag=flag,
            violations=violations,
            warnings=warnings,
            passed_rules=passed
        )

    def _extract_all_text(self, output: Dict[str, Any]) -> str:
        """Estrae tutto il testo da un output per analisi."""
        texts = []

        # Video prompts
        for scene in output.get("video_triptych", []):
            if "prompt" in scene:
                texts.append(scene["prompt"])
            if "mood_tags" in scene:
                texts.extend(scene["mood_tags"])

        # OST prompt
        ost = output.get("ost_prompt", {})
        if "prompt" in ost:
            texts.append(ost["prompt"])
        if "mood" in ost:
            texts.append(ost["mood"])

        return " ".join(texts).lower()

    def _check_blacklist(self, text: str) -> List[PolicyViolation]:
        """Cerca termini in blacklist."""
        violations = []
        text_lower = text.lower()

        for term in self.BLACKLIST_TERMS:
            # Word boundary match
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, text_lower):
                violations.append(PolicyViolation(
                    rule_id="R001",
                    rule_name="blacklist_term",
                    severity=PolicyFlag.RED,
                    message=f"Blacklisted term found: '{term}'",
                    context=self._get_context(text, term)
                ))

        return violations

    def _check_warnings(self, text: str) -> List[PolicyViolation]:
        """Cerca termini che generano warning."""
        warnings = []
        text_lower = text.lower()

        for term in self.WARNING_TERMS:
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, text_lower):
                warnings.append(PolicyViolation(
                    rule_id="R002",
                    rule_name="warning_term",
                    severity=PolicyFlag.YELLOW,
                    message=f"Warning term found: '{term}' - review recommended",
                    context=self._get_context(text, term)
                ))

        return warnings

    def _check_marine_vocabulary(self, text: str) -> List[PolicyViolation]:
        """Verifica presenza di vocabolario marino."""
        text_lower = text.lower()
        found_marine = sum(1 for term in self.MARINE_VOCABULARY if term in text_lower)

        # Richiedi almeno 5 termini marini
        if found_marine < 5:
            return [PolicyViolation(
                rule_id="R003",
                rule_name="marine_vocabulary",
                severity=PolicyFlag.YELLOW,
                message=f"Low marine vocabulary: only {found_marine} terms found (expected >= 5)"
            )]
        return []

    def _check_structure(self, output: Dict[str, Any]) -> List[PolicyViolation]:
        """Verifica struttura output."""
        violations = []

        # Check video_triptych
        triptych = output.get("video_triptych", [])
        if not triptych:
            violations.append(PolicyViolation(
                rule_id="R004a",
                rule_name="missing_triptych",
                severity=PolicyFlag.RED,
                message="video_triptych is missing or empty"
            ))
        elif len(triptych) != 3:
            violations.append(PolicyViolation(
                rule_id="R004b",
                rule_name="wrong_scene_count",
                severity=PolicyFlag.RED,
                message=f"Expected 3 scenes, got {len(triptych)}"
            ))

        # Check OST
        ost = output.get("ost_prompt", {})
        if not ost or not ost.get("prompt"):
            violations.append(PolicyViolation(
                rule_id="R004c",
                rule_name="missing_ost",
                severity=PolicyFlag.RED,
                message="ost_prompt is missing or has no prompt"
            ))

        return violations

    def _check_scene_sequence(self, output: Dict[str, Any]) -> List[PolicyViolation]:
        """Verifica sequenza scene start→evolve→end."""
        violations = []
        triptych = output.get("video_triptych", [])

        if len(triptych) >= 3:
            roles = [s.get("scene_role") for s in triptych]
            expected = ["start", "evolve", "end"]

            if roles != expected:
                violations.append(PolicyViolation(
                    rule_id="R005",
                    rule_name="wrong_sequence",
                    severity=PolicyFlag.RED,
                    message=f"Scene sequence should be {expected}, got {roles}"
                ))

        return violations

    def _check_archetype_consistency(
        self,
        output: Dict[str, Any],
        profile: Dict[str, Any]
    ) -> List[PolicyViolation]:
        """Verifica coerenza con archetipo del profilo."""
        warnings = []

        # Estrai archetipo dal profilo
        user_profile = profile.get("user_profile", profile)
        archetype = user_profile.get("primary_archetype", "").lower()

        if archetype not in self.ARCHETYPE_KEYWORDS:
            return []  # Can't check unknown archetype

        # Conta keyword dell'archetipo corretto vs altri
        text = self._extract_all_text(output)
        correct_keywords = self.ARCHETYPE_KEYWORDS[archetype]
        correct_count = sum(1 for kw in correct_keywords if kw in text)

        # Conta keyword di altri archetipi
        other_count = 0
        for other_arch, keywords in self.ARCHETYPE_KEYWORDS.items():
            if other_arch != archetype:
                other_count += sum(1 for kw in keywords if kw in text)

        # Warning se più keyword di altri archetipi
        if other_count > correct_count * 1.5:
            warnings.append(PolicyViolation(
                rule_id="R006",
                rule_name="archetype_mismatch",
                severity=PolicyFlag.YELLOW,
                message=f"Output may not match {archetype} archetype (correct: {correct_count}, other: {other_count})"
            ))

        return warnings

    def _check_prompt_lengths(self, output: Dict[str, Any]) -> List[PolicyViolation]:
        """Verifica lunghezza prompt."""
        warnings = []

        for i, scene in enumerate(output.get("video_triptych", [])):
            prompt = scene.get("prompt", "")
            if len(prompt) < 50:
                warnings.append(PolicyViolation(
                    rule_id="R007a",
                    rule_name="prompt_too_short",
                    severity=PolicyFlag.YELLOW,
                    message=f"Scene {i+1} prompt is too short ({len(prompt)} chars, expected >= 50)"
                ))
            elif len(prompt) > 500:
                warnings.append(PolicyViolation(
                    rule_id="R007b",
                    rule_name="prompt_too_long",
                    severity=PolicyFlag.YELLOW,
                    message=f"Scene {i+1} prompt is too long ({len(prompt)} chars, expected <= 500)"
                ))

        return warnings

    def _get_context(self, text: str, term: str, window: int = 50) -> str:
        """Estrae contesto attorno a un termine."""
        idx = text.lower().find(term.lower())
        if idx == -1:
            return ""

        start = max(0, idx - window)
        end = min(len(text), idx + len(term) + window)
        return f"...{text[start:end]}..."
