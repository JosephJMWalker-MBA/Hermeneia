# Hermeneia Architecture Blueprint

## Core Insight

Hermeneia is not merely a reading app, note-taking tool, or Ai chatbot.

Hermeneia is a semantic study environment where the user's act of reading becomes structured, ranked, machine-readable interpretation.

The editor is a semantic markup engine disguised as a study interface.

The user appears to be highlighting, bucketing, asking questions, making observations, ranking importance, and connecting themes. Underneath, Hermeneia is creating a better marked document for the machine to reason over.

This is the central implementation principle:

> The user marks meaning. The machine reasons over the marked meaning.

Hermeneia should not replace interpretation. It should preserve, structure, test, and extend the user's interpretive work.

---

## Why This Matters

Many Ai study tools begin with the machine:

> Ask Ai a question about this text.

Hermeneia begins with the human:

> Mark what you see. Then let the system help you understand what your markings reveal.

That distinction is foundational.

The user's attention is the source signal. The machine's role is to serve that signal.

---

## Languages Should Be Used According to Their Purpose

A key architectural insight is that each language or layer should do what it was created to do.

HTML is not merely a way to display pages. It is a semantic language for structuring information.

CSS is not merely decoration. It is a language for visual communication, hierarchy, emphasis, rhythm, contrast, and accessibility.

JavaScript is not merely interactivity. It is a language for behavior, state, response, and dynamic transformation.

Databases are not merely storage. They preserve structured memory, relationships, history, and retrieval.

Ai is not merely generation. It reasons over structured context, detects patterns, proposes next steps, and helps transform marked understanding into usable outputs.

Hermeneia should honor these purposes instead of flattening everything into a generic app interface.

---

## Layer 0 — Source

Source is the original material being studied.

Examples:

- Scripture
- Books
- Articles
- Research papers
- Legal documents
- Contracts
- Notes
- Sermons
- Transcripts
- Curricula
- Public-domain texts

The source should remain preserved separately from user annotations.

Principle:

> Do not corrupt the source. Mark meaning around it and over it.

Initial model:

```ts
export interface HermeneiaDocument {
  id: string;
  title: string;
  sourceType: "scripture" | "book" | "article" | "paper" | "contract" | "notes" | "other";
  rawText: string;
  semanticHtml?: string;
  createdAt: string;
  updatedAt: string;
}
```

---

## Layer 1 — Semantic Structure

Semantic structure identifies what parts of the document are.

Examples:

- Title
- Section
- Heading
- Paragraph
- Quotation
- Citation
- Definition
- Figure
- Timeline/date
- Aside/commentary
- Cross-reference
- Table
- List

This is where HTML's purpose becomes foundational. HTML gives the machine and the user a shared structure before interpretation begins.

Possible semantic mappings:

| Hermeneia object | Semantic basis |
| --- | --- |
| Primary passage | `<article>` / `<section>` |
| Cross-reference | `<a>` |
| Citation | `<cite>` |
| Quotation | `<blockquote>` |
| Definition | `<dfn>` |
| Highlighted observation | `<mark>` |
| Commentary note | `<aside>` |
| Expandable study note | `<details>` / `<summary>` |
| Timeline/date | `<time>` |
| Confidence/completion | `<meter>` / `<progress>` |
| Lexical term | `<abbr>`, `<dfn>`, `<data>` |

Principle:

> Semantic structure comes before Ai interpretation.

---

## Layer 2 — Human Interpretation

Human interpretation is where Hermeneia becomes distinct.

The user marks what they see.

Primary interpretive actions:

- Observe
- Question
- Bucket
- Rank
- Connect
- Resolve

Secondary interpretive actions:

- Define
- Cite
- Compare
- Promote
- Demote

These actions create structured claims about the text.

A highlight is not merely a color.

A note is not merely a note.

A bucket is not merely a folder.

A rank is not merely a rating.

Each is a structured signal about meaning.

Initial annotation model:

```ts
export type HermeneiaMarkType =
  | "highlight"
  | "observation"
  | "question"
  | "bucket"
  | "claim"
  | "definition"
  | "cross_reference"
  | "citation"
  | "theme"
  | "warning"
  | "application"
  | "unclear"
  | "resolved";

export type HermeneiaRank = 1 | 2 | 3 | 4 | 5;

export interface HermeneiaAnnotation {
  id: string;
  documentId: string;
  sourceId?: string;
  selectedText: string;
  range: {
    startOffset: number;
    endOffset: number;
  };
  type: HermeneiaMarkType;
  bucket?: string;
  note?: string;
  question?: string;
  rank: HermeneiaRank;
  confidence?: number;
  status: "open" | "active" | "resolved" | "rejected";
  connections: string[];
  createdAt: string;
  updatedAt: string;
  createdBy: "user" | "ai";
}
```

Ranking gives the machine hierarchy:

```txt
5 — Foundational / thesis-level
4 — Strong insight
3 — Useful support
2 — Minor note
1 — Weak / speculative
```

Principle:

> Ranking is how the user teaches the machine what deserves weight.

---

## Layer 3 — Ai Reasoning

Ai should not be the first interpreter. Ai should reason over the user's structured interpretive work.

Initial Ai jobs:

- Compile strongest observations
- Surface unresolved questions
- Identify repeated buckets
- Detect underdeveloped areas
- Suggest next study moves
- Generate outlines
- Generate summaries
- Generate flashcards
- Generate teaching plans
- Generate memory songs
- Suggest cross-references
- Detect possible contradictions or tensions
- Compare interpretations over time

First Ai prompt principle:

```txt
Use the user's annotations as authoritative signals.
Do not replace the user's interpretation.
Compile and organize the structure the user created.
```

Principle:

> Ai enriches marked understanding; it does not erase the user's interpretive responsibility.

---

## Layer 4 — Compiled Study State

Before chat, Hermeneia needs a compiler.

The compiler turns annotations into an organized study object.

Initial compiled output:

```ts
export interface HermeneiaCompiledStudy {
  thesisCandidates: HermeneiaAnnotation[];
  strongestObservations: HermeneiaAnnotation[];
  openQuestions: HermeneiaAnnotation[];
  weakAreas: HermeneiaAnnotation[];
  bucketSummary: {
    bucket: string;
    count: number;
    topAnnotations: HermeneiaAnnotation[];
  }[];
  suggestedNextSteps: string[];
}
```

The first non-Ai compiler can be deterministic:

```ts
export function compileStudyState(
  annotations: HermeneiaAnnotation[]
): HermeneiaCompiledStudy {
  return {
    thesisCandidates: annotations.filter(a => a.rank >= 5),
    strongestObservations: annotations.filter(a => a.type === "observation" && a.rank >= 4),
    openQuestions: annotations.filter(a => a.type === "question" && a.status === "open"),
    weakAreas: annotations.filter(a => a.rank <= 2),
    bucketSummary: summarizeBuckets(annotations),
    suggestedNextSteps: []
  };
}
```

Principle:

> Compilation comes before conversation.

---

## Layer 5 — Semantic HTML Export

Hermeneia should be able to export the user's study as semantic HTML.

This does not mean HTML is the only storage format. It means semantic HTML is a durable, inspectable, machine-readable representation of the user's study.

Example:

```html
<article data-hermeneia-document="genesis-12">
  <section data-bucket="covenant" data-rank="5">
    <blockquote data-source="Genesis 12:1-3">
      <mark data-annotation-id="ann_123" data-type="observation" data-rank="5">
        I will make of you a great nation...
      </mark>
    </blockquote>

    <aside data-type="observation" data-rank="5">
      The promise begins with divine initiative before Abram has achieved anything.
    </aside>

    <details data-type="question" data-status="open" data-rank="4">
      <summary>Why is land promised before nationhood?</summary>
      <p>This may connect to Eden, exile, and restoration patterns.</p>
    </details>
  </section>
</article>
```

Principle:

> Export should preserve meaning, not just appearance.

---

## Layer 6 — Knowledge Graph

Once multiple documents and studies exist, Hermeneia can connect them.

Examples:

- Repeated themes across books
- Cross-document references
- Questions that recur over time
- User's changing understanding
- High-rank insights across a library
- Buckets that become theological, philosophical, legal, or research categories
- Concepts that move from unresolved to resolved
- Patterns that become publishable work

This is where Hermeneia becomes more than a study app. It becomes a long-term knowledge system.

Principle:

> Hermeneia should remember the path of understanding, not just the final answer.

---

## MVP Screen

The first MVP only needs one focused screen.

```txt
------------------------------------------------
Document title

[ Passage / book text on left ]

[ Study panel on right ]
- Buckets
- Observations
- Questions
- Ranked insights
- Open items

Toolbar:
Observe | Question | Bucket | Rank | Connect | Resolve

Bottom:
[Compile Study]
[Export Semantic HTML]
[Generate Outline]
------------------------------------------------
```

Minimum loop:

```txt
select text
→ mark meaning
→ assign bucket/rank
→ compile study
→ export structured output
```

---

## Development Priority

Do not begin with the beautiful reader.

Begin with the annotation object model.

Then build:

1. Types
2. Reducer/state management
3. Selection capture
4. Annotation creation
5. Bucket/rank UI
6. Side panel
7. Deterministic compiler
8. Semantic HTML export
9. Ai compiler enhancement
10. Reader polish

Suggested file paths:

```txt
src/lib/hermeneia/types.ts
src/lib/hermeneia/reducer.ts
src/lib/hermeneia/compiler.ts
src/lib/hermeneia/semantic-html.ts
src/components/hermeneia/SemanticStudyEditor.tsx
src/components/hermeneia/AnnotationToolbar.tsx
src/components/hermeneia/StudyPanel.tsx
src/components/hermeneia/CompiledStudyPanel.tsx
```

---

## Guardrails

Hermeneia should avoid these traps:

- Becoming just another Ai chat-with-a-book app
- Treating annotations as generic comments
- Treating highlights as visual decoration
- Letting Ai replace the user's interpretive work
- Building a beautiful interface before the meaning model exists
- Flattening rank, confidence, bucket, and question status into plain text notes
- Losing the original source text

---

## Philosophical Anchor

Hermeneia is about rightly handling meaning.

The software pattern is simple:

1. Preserve the source.
2. Mark the structure.
3. Record the user's observations.
4. Rank what matters.
5. Keep questions open until resolved.
6. Let Ai serve the marked understanding.
7. Preserve the path of interpretation over time.

Scriptural anchor:

> Study to shew thyself approved unto God, a workman that needeth not to be ashamed, rightly dividing the word of truth.

The system should help the user rightly divide, not outsource discernment.

---

## Final Principle

Hermeneia turns study into semantic markup.

That is the engine.

Everything else is interface, storage, or output.