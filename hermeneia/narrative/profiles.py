"""
ExpressionProfile registry and built-in profiles.

An ExpressionProfile is not a presentation style. It is a complete specification
of how meaning should be realized in language. The Architect Plan is invariant
across all profiles — including translations. Meaning is stable; expression adapts.

Profile slug convention: {register}-{language}
  literary-en, historical-en, psychoanalytic-en
  literary-zh, literary-sw, literary-es, literary-fr, childrens-en, executive-en
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..storage.hashing import make_expression_profile_id

# ── Built-in profile definitions ──────────────────────────────────────────────

BUILT_IN_PROFILES: list[dict] = [
    {
        "slug": "childrens-en",
        "name": "Children's",
        "description": "Renders meaning through concrete imagery, wonder, and accessible narrative for young readers.",
        "language": "en",
        "audience": "children (ages 8–12)",
        "reading_level": "elementary",
        "tone": "warm, curious, concrete",
        "voice": "second-person or close third-person",
        "artist_prompt": (
            "Write for a curious ten-year-old who loves stories. "
            "Use short sentences and concrete images — no abstractions, no jargon. "
            "Every idea must be visible or feelable. "
            "Make the reader feel wonder, not confusion. "
            "Anchor every claim to something a child can picture."
        ),
        "critic_expectations": (
            "Readable aloud. No words that require a dictionary. "
            "Every idea has a physical anchor. "
            "No passive voice. No dependent clauses longer than eight words. "
            "Should feel like a story, not a lecture."
        ),
    },
    {
        "slug": "executive-en",
        "name": "Executive",
        "description": "Renders meaning as a briefing: evidence-first, action-oriented, no decoration.",
        "language": "en",
        "audience": "senior decision-maker",
        "reading_level": "professional",
        "tone": "direct, precise, consequential",
        "voice": "third-person declarative",
        "artist_prompt": (
            "Write for a senior executive with three minutes. "
            "Lead with the conclusion. Support with evidence. End with implication. "
            "No passive voice. No scene-setting. No throat-clearing. "
            "Every sentence must earn its place or be cut. "
            "Density over decoration."
        ),
        "critic_expectations": (
            "Conclusion in the first sentence. "
            "Evidence cited without elaboration. "
            "Implication stated explicitly. "
            "No metaphors, no rhetorical questions, no hedged conclusions. "
            "Would survive being forwarded in an email."
        ),
    },
    {
        "slug": "literary-en",
        "name": "Literary",
        "description": "Reads the text as an aesthetic object. Attends to form, symbol, and how expression enacts meaning.",
        "language": "en",
        "audience": "academic",
        "reading_level": "undergraduate",
        "tone": "analytical",
        "voice": "third-person critical",
        "artist_prompt": (
            "Attend to symbol, motif, narrative arc, and figurative language. "
            "Ground every claim in the texture of the prose — diction, rhythm, imagery. "
            "Treat the text as an aesthetic object whose form enacts its meaning. "
            "Write as a literary critic, not a plot summarizer."
        ),
        "critic_expectations": (
            "Reads as criticism, not summary. Names specific formal devices. "
            "Distinguishes what the text does from what it says. "
            "Avoids plot recounting. Every sentence earns its place."
        ),
    },
    {
        "slug": "historical-en",
        "name": "Historical",
        "description": "Situates the text within the material and ideological conditions of its production.",
        "language": "en",
        "audience": "academic",
        "reading_level": "undergraduate",
        "tone": "analytical",
        "voice": "third-person critical",
        "artist_prompt": (
            "Attend to social context, period conditions, material forces, and ideological formations. "
            "Situate the text within the historical moment of its production and reception. "
            "Read the observations as symptoms of class, race, economy, or political structure."
        ),
        "critic_expectations": (
            "Names specific historical forces, not vague 'society'. "
            "Connects textual details to documented period conditions. "
            "Distinguishes what the text reflects from what it obscures. "
            "Avoids anachronism."
        ),
    },
    {
        "slug": "psychoanalytic-en",
        "name": "Psychoanalytic",
        "description": "Reads the text for desire, displacement, and the movement between manifest and latent content.",
        "language": "en",
        "audience": "academic",
        "reading_level": "graduate",
        "tone": "analytical",
        "voice": "third-person critical",
        "artist_prompt": (
            "Attend to desire, displacement, repetition, and the unconscious. "
            "Read symptoms: what is repressed, deferred, or returned. "
            "Track the movement between manifest and latent content. "
            "Draw on the observations as evidence of psychic structure, not character psychology."
        ),
        "critic_expectations": (
            "Names the structural dynamic, not just motivation. "
            "Uses the register of desire and lack. "
            "Every interpretive claim is traceable to textual evidence. "
            "Avoids pop-psychology reduction."
        ),
    },
    {
        "slug": "literary-es",
        "name": "Literary (Spanish)",
        "description": "Renders the same semantic contract as literary-en through Spanish idiom, rhythm, and literary tradition.",
        "language": "es",
        "audience": "academic",
        "reading_level": "undergraduate",
        "tone": "analytical",
        "voice": "third-person critical",
        "artist_prompt": (
            "Escribe en español académico y literario. "
            "Presta atención a los símbolos, las imágenes y la estructura narrativa. "
            "Cada afirmación debe estar fundamentada en el texto — en las palabras, el ritmo, las figuras retóricas. "
            "Trata el texto como un objeto estético cuya forma realiza su significado. "
            "Escribe como crítico literario, no como resumidor de tramas."
        ),
        "critic_expectations": (
            "Reads as literary criticism in Spanish. "
            "Names specific formal devices using Spanish critical vocabulary where available. "
            "Distinguishes what the text does from what it says. "
            "Avoids plot summary. Semantic commitments must match the Architect Plan exactly."
        ),
    },
    {
        "slug": "literary-fr",
        "name": "Literary (French)",
        "description": "Renders the same semantic contract as literary-en through French idiom, rhythm, and literary tradition.",
        "language": "fr",
        "audience": "academic",
        "reading_level": "undergraduate",
        "tone": "analytical",
        "voice": "third-person critical",
        "artist_prompt": (
            "Rédigez en français académique et littéraire. "
            "Prêtez attention aux symboles, aux images et à la structure narrative. "
            "Chaque affirmation doit être ancrée dans le texte — dans les mots, le rythme, les figures rhétoriques. "
            "Traitez le texte comme un objet esthétique dont la forme réalise le sens. "
            "Écrivez en critique littéraire, non en résumeur d'intrigue."
        ),
        "critic_expectations": (
            "Reads as literary criticism in French. "
            "Names specific formal devices using French critical vocabulary where available. "
            "Distinguishes what the text does from what it says. "
            "Avoids plot summary. Semantic commitments must match the Architect Plan exactly."
        ),
    },
    {
        "slug": "literary-zh",
        "name": "Literary (Mandarin)",
        "description": "Renders the same semantic contract as literary-en through Mandarin idiom, rhythm, and literary tradition.",
        "language": "zh",
        "audience": "academic",
        "reading_level": "undergraduate",
        "tone": "analytical",
        "voice": "third-person critical",
        "artist_prompt": (
            "用学术性的文学中文写作。"
            "关注象征、意象和叙事结构。"
            "每一个论断都必须植根于文本——词语、节奏、修辞手法。"
            "将文本视为形式与意义相互实现的审美对象。"
            "以文学批评家的身份写作，而非情节摘要者。"
        ),
        "critic_expectations": (
            "Reads as literary criticism in Mandarin Chinese. "
            "Names specific formal devices using Chinese critical vocabulary where available. "
            "Distinguishes what the text does from what it says. "
            "Avoids plot summary. Semantic commitments must match the Architect Plan exactly."
        ),
    },
    {
        "slug": "literary-sw",
        "name": "Literary (Swahili)",
        "description": "Renders the same semantic contract as literary-en through Swahili idiom, rhythm, and literary tradition.",
        "language": "sw",
        "audience": "academic",
        "reading_level": "undergraduate",
        "tone": "analytical",
        "voice": "third-person critical",
        "artist_prompt": (
            "Andika kwa Kiswahili fasaha cha fasihi. "
            "Zingatia ishara, taswira, na mpangilio wa hadithi. "
            "Kila dai lazima liwe na msingi katika maandishi — maneno, mdundo, picha. "
            "Tibu maandishi kama kitu cha sanaa ambaye umbo lake unatekeleza maana yake. "
            "Andika kama mkosoaji wa fasihi, si mfupishaji wa hadithi."
        ),
        "critic_expectations": (
            "Reads as literary criticism in Swahili. "
            "Names specific formal devices using Swahili critical vocabulary where available. "
            "Distinguishes what the text does from what it says. "
            "Avoids plot summary. Semantic commitments must match the Architect Plan exactly."
        ),
    },
]


def seed_built_in_profiles(conn: sqlite3.Connection) -> None:
    """Insert built-in profiles if not present. Idempotent (INSERT OR IGNORE)."""
    now = datetime.now(timezone.utc).isoformat()
    for defn in BUILT_IN_PROFILES:
        profile_id = make_expression_profile_id(defn["slug"])
        conn.execute(
            """
            INSERT OR IGNORE INTO expression_profiles
                (id, slug, name, description, language, audience, reading_level,
                 tone, voice, artist_prompt, critic_expectations, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'built-in', ?)
            """,
            (
                profile_id, defn["slug"], defn["name"], defn["description"],
                defn["language"], defn["audience"], defn["reading_level"],
                defn["tone"], defn["voice"],
                defn["artist_prompt"], defn["critic_expectations"],
                now,
            ),
        )
    conn.commit()


def get_profile(slug: str, conn: sqlite3.Connection) -> dict | None:
    row = conn.execute("SELECT * FROM expression_profiles WHERE slug = ?", (slug,)).fetchone()
    return dict(row) if row else None


def list_profiles(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM expression_profiles ORDER BY source DESC, language ASC, name ASC"
    ).fetchall()
    return [dict(r) for r in rows]
