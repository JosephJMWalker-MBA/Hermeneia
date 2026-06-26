"""
Tests for profile fidelity evaluation.

Verifies the four properties the user specified:
  1. Children's profile flags jargon and abstraction.
  2. Executive profile flags throat-clearing and buried conclusions.
  3. Semantic fidelity can pass while profile fidelity fails.
  4. Profile expectations do not change required observations/claims.
"""
import json
import pytest

from hermeneia.compiler.critic.profile_fidelity import check_profile_fidelity
from hermeneia.compiler.critic.narrative_fidelity import validate


# ── Fixtures ───────────────────────────────────────────────────────────────────

PROFILE_CHILDRENS = {
    "slug": "childrens-en",
    "name": "Children's",
    "critic_expectations": (
        "Readable aloud. No words that require a dictionary. "
        "No passive voice. No dependent clauses longer than eight words."
    ),
}

PROFILE_EXECUTIVE = {
    "slug": "executive-en",
    "name": "Executive",
    "critic_expectations": (
        "Conclusion in the first sentence. No rhetorical questions. "
        "No hedged conclusions. Would survive being forwarded in an email."
    ),
}

PROFILE_LITERARY = {
    "slug": "literary-en",
    "name": "Literary",
    "critic_expectations": (
        "Reads as criticism, not summary. Names specific formal devices. "
        "Avoids plot recounting."
    ),
}

PROFILE_PSYCHOANALYTIC = {
    "slug": "psychoanalytic-en",
    "name": "Psychoanalytic",
    "critic_expectations": (
        "Names the structural dynamic. Uses the register of desire and lack. "
        "Avoids pop-psychology reduction."
    ),
}

PROFILE_UNREGISTERED = {
    "slug": "pastoral-en",
    "name": "Pastoral",
    "critic_expectations": "Write about nature.",
}


# ── 1. Children's: flags jargon and abstraction ───────────────────────────────

class TestChildrensProfile:
    GOOD = (
        "Gatsby wants to win Daisy back. He throws big parties so she might come. "
        "The green light at the end of the dock is his hope. "
        "He looks at it every night and wishes."
    )
    BAD_LONG_WORDS = (
        "Gatsby's existentialist predicament manifests as a representational "
        "abstraction of his unattainable aspirations. The phenomenological "
        "underpinnings of his circumstantial melancholy are unmistakable."
    )
    BAD_PASSIVE = (
        "The party was thrown by Gatsby. The green light was seen by Nick. "
        "The dream was pursued endlessly. The truth was hidden carefully."
    )
    BAD_LONG_SENTENCES = (
        "Gatsby, who had always believed that wealth and determination could bridge "
        "any distance no matter how vast or seemingly insurmountable, organised "
        "lavish parties every weekend in the hope that Daisy, the woman he had "
        "loved and lost years before, might one day wander across the bay to find him."
    )

    def test_good_text_passes(self):
        result = check_profile_fidelity(self.GOOD, PROFILE_CHILDRENS)
        assert result["profile_fidelity_score"] == 100.0
        assert result["profile_approved"] is True

    def test_jargon_flagged(self):
        result = check_profile_fidelity(self.BAD_LONG_WORDS, PROFILE_CHILDRENS)
        long_word_check = next(
            c for c in result["checks"] if "characters" in c["expectation"]
        )
        assert long_word_check["passed"] is False

    def test_passive_voice_flagged(self):
        result = check_profile_fidelity(self.BAD_PASSIVE, PROFILE_CHILDRENS)
        passive_check = next(
            c for c in result["checks"] if "passive" in c["expectation"].lower()
        )
        assert passive_check["passed"] is False

    def test_long_sentence_flagged(self):
        result = check_profile_fidelity(self.BAD_LONG_SENTENCES, PROFILE_CHILDRENS)
        length_check = next(
            c for c in result["checks"] if "exceeds" in c["expectation"].lower()
        )
        assert length_check["passed"] is False

    def test_score_below_100_when_checks_fail(self):
        result = check_profile_fidelity(self.BAD_PASSIVE, PROFILE_CHILDRENS)
        assert result["profile_fidelity_score"] < 100.0


# ── 2. Executive: flags throat-clearing and buried conclusions ─────────────────

class TestExecutiveProfile:
    GOOD = (
        "Gatsby's pursuit of Daisy represents a fundamental misreading of wealth "
        "as a substitute for identity. The evidence is clear: his parties are "
        "performances, not celebrations. Leaders should treat aspiration without "
        "accountability as a structural risk."
    )
    BAD_QUESTION_OPENING = (
        "What does it mean to want something you can never have? "
        "Gatsby perhaps embodies this tension. It seems he might be chasing an illusion."
    )
    BAD_HEDGING = (
        "Gatsby arguably demonstrates perhaps the most interesting case of self-delusion "
        "in American literature. One might argue that his behaviour seems to suggest "
        "an inability to distinguish aspiration from obsession."
    )

    def test_good_text_passes_declarative(self):
        result = check_profile_fidelity(self.GOOD, PROFILE_EXECUTIVE)
        declarative_check = next(
            c for c in result["checks"] if "declarative" in c["expectation"].lower()
        )
        assert declarative_check["passed"] is True

    def test_question_opening_flagged(self):
        result = check_profile_fidelity(self.BAD_QUESTION_OPENING, PROFILE_EXECUTIVE)
        declarative_check = next(
            c for c in result["checks"] if "declarative" in c["expectation"].lower()
        )
        assert declarative_check["passed"] is False

    def test_hedging_flagged(self):
        result = check_profile_fidelity(self.BAD_HEDGING, PROFILE_EXECUTIVE)
        hedge_check = next(
            c for c in result["checks"] if "hedge" in c["expectation"].lower()
        )
        assert hedge_check["passed"] is False

    def test_rhetorical_question_flagged(self):
        result = check_profile_fidelity(self.BAD_QUESTION_OPENING, PROFILE_EXECUTIVE)
        q_check = next(
            c for c in result["checks"] if "rhetorical" in c["expectation"].lower()
        )
        assert q_check["passed"] is False


# ── 3. Semantic fidelity can pass while profile fidelity fails ─────────────────

class TestSeparationOfConcerns:
    """
    A narrative can satisfy all Architect Plan semantic commitments
    while still failing the profile's expression contract.
    """

    def _minimal_plan(self, title="Test Plan"):
        return {
            "id": "plan-001",
            "title": title,
            "blueprint_id": "bp-001",
        }

    def _paragraph_with_term(self, term: str, priority: str = "critical"):
        return {
            "plan_id": "plan-001",
            "order_idx": 0,
            "purpose": "test",
            "required_observations": "[]",
            "required_interpretations": "[]",
            "required_terms": json.dumps([{"term": term, "priority": priority}]),
            "forbidden_claims": "[]",
        }

    def test_semantic_pass_profile_fail(self):
        """
        Text contains the required term (semantic ✓) but uses passive voice
        and jargon, violating the Children's expression contract (profile ✗).
        """
        required_term = "aspiration"
        text = (
            "The existential manifestation of aspiration was observed by the "
            "protagonist in the phenomenological context of his socioeconomic "
            "displacement. The dream was perpetuated indefinitely."
        )
        narrative = {
            "id": "rn-001",
            "architect_plan_id": "plan-001",
            "expression_profile_id": "ep-001",
            "text": text,
        }
        plan = self._minimal_plan()
        paras = [self._paragraph_with_term(required_term)]

        validation = validate(plan, paras, narrative, profile=PROFILE_CHILDRENS)

        # Semantic fidelity: required term present → should be 100%
        assert validation["semantic_fidelity"] == 100.0

        # Profile fidelity: passive voice + jargon → should fail
        pf = json.loads(validation["profile_fidelity"])
        assert pf["profile_fidelity_score"] < 100.0
        failing = [c for c in pf["checks"] if not c["passed"]]
        assert len(failing) >= 1, "At least one expression check should fail"

    def test_profile_fidelity_none_when_no_profile(self):
        """Without a profile, profile_fidelity is None — semantic check still runs."""
        narrative = {
            "id": "rn-002",
            "architect_plan_id": "plan-001",
            "expression_profile_id": None,
            "text": "Gatsby aspires to reclaim the past.",
        }
        plan = self._minimal_plan()
        paras = [self._paragraph_with_term("aspiration")]
        validation = validate(plan, paras, narrative, profile=None)

        assert validation["profile_fidelity"] is None
        assert validation["semantic_fidelity"] is not None


# ── 4. Profile expectations do not alter required observations/claims ──────────

class TestProfileDoesNotAlterMeaning:
    """Profile selection must not change what terms, observations, or
    interpretations the Critic requires from the Architect Plan."""

    def _plan_and_para(self, terms):
        plan = {"id": "plan-x", "title": "X", "blueprint_id": "bp-x"}
        paras = [{
            "plan_id": "plan-x", "order_idx": 0, "purpose": "test",
            "required_observations": "[]", "required_interpretations": "[]",
            "required_terms": json.dumps(
                [{"term": t, "priority": "critical"} for t in terms]
            ),
            "forbidden_claims": "[]",
        }]
        return plan, paras

    def _narrative(self, text):
        return {
            "id": "rn-x", "architect_plan_id": "plan-x",
            "expression_profile_id": "ep-x", "text": text,
        }

    def test_same_terms_required_regardless_of_profile(self):
        terms = ["aspiration", "illusion", "decay"]
        text_with_terms = "aspiration illusion decay"
        plan, paras = self._plan_and_para(terms)

        result_childrens = validate(
            plan, paras, self._narrative(text_with_terms), profile=PROFILE_CHILDRENS
        )
        result_executive = validate(
            plan, paras, self._narrative(text_with_terms), profile=PROFILE_EXECUTIVE
        )

        # Both profiles must yield the same semantic fidelity for the same text
        assert result_childrens["semantic_fidelity"] == result_executive["semantic_fidelity"]
        assert result_childrens["required_terms_present"] == result_executive["required_terms_present"]
        assert result_childrens["required_terms_missing"] == result_executive["required_terms_missing"]

    def test_profile_fidelity_reports_different_results(self):
        """The same text yields different profile_fidelity results per profile,
        proving the separation is real."""
        terms = ["aspiration"]
        # Text that passes Executive but fails Children's (long words, passive)
        text = (
            "Gatsby's unattainable aspirations were embodied in his obsessive "
            "accumulation of wealth. Aspiration here is misidentified with destiny."
        )
        plan, paras = self._plan_and_para(terms)

        result_exec = validate(
            plan, paras, self._narrative(text), profile=PROFILE_EXECUTIVE
        )
        result_child = validate(
            plan, paras, self._narrative(text), profile=PROFILE_CHILDRENS
        )

        pf_exec = json.loads(result_exec["profile_fidelity"])
        pf_child = json.loads(result_child["profile_fidelity"])

        # Semantic fidelity identical (same plan, same text)
        assert result_exec["semantic_fidelity"] == result_child["semantic_fidelity"]

        # Profile fidelity differs
        assert pf_exec["profile_slug"] == "executive-en"
        assert pf_child["profile_slug"] == "childrens-en"
        # At least one score differs (different checks)
        assert pf_exec["profile_fidelity_score"] != pf_child["profile_fidelity_score"]


# ── 5. Unregistered profiles return graceful not-implemented ───────────────────

def test_unregistered_profile_graceful():
    result = check_profile_fidelity("Some text.", PROFILE_UNREGISTERED)
    assert result["checks"] == []
    assert result["profile_fidelity_score"] is None
    assert result["profile_approved"] is None
    assert "note" in result


# ── 6. Psychoanalytic vocabulary detection ────────────────────────────────────

def test_psychoanalytic_vocabulary_detected():
    text = (
        "The green light operates as an object of desire — always deferred, never "
        "possessed. Gatsby's compulsive repetition of the past reveals a fundamental "
        "lack at the core of his self-image. The unconscious drive toward Daisy "
        "displaces a more primitive anxiety."
    )
    result = check_profile_fidelity(text, PROFILE_PSYCHOANALYTIC)
    vocab_check = next(c for c in result["checks"] if "psychoanalytic" in c["expectation"].lower())
    assert vocab_check["passed"] is True


def test_psychoanalytic_pop_psychology_flagged():
    text = (
        "Gatsby's self-esteem was damaged by his childhood. "
        "His toxic relationship with wealth became a coping mechanism. "
        "He needed closure from his healing journey."
    )
    result = check_profile_fidelity(text, PROFILE_PSYCHOANALYTIC)
    pop_check = next(c for c in result["checks"] if "pop" in c["expectation"].lower())
    assert pop_check["passed"] is False
