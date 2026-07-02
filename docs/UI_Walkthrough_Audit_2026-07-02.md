Verified: **PR \#3 is open, mergeable, not draft, 3 commits, 1 file changed, \+57/-31**. It is exactly scoped to Motif Panel hardening and data honesty.

My read: **merge PR \#3.** It fixes a real trust issue, not just polish.

The important takeaway from that handoff is this:

PR \#2 made the Pattern View’s words truthful.

PR \#3 makes the Pattern View’s mechanics truthful.

That matters because Hermeneia cannot say “evidence boundary” while letting the UI imply multi-evidence generation that the backend does not actually perform. PR \#3 fixes that by replacing checkboxes with radios, defaulting to the first primary-corpus occurrence, and making the Lab card explicitly say only the chosen passage is sent while the rest remain for comparison.

The second major win is **data honesty**. The agent found that the supposedly uncapped fetch is still clamped to 100 server-side, so for “Gatsby” the UI was effectively saying “100 total” when the true count was 492\. PR \#3 now discloses “showing the first 100 of 492 occurrences” and warns that the pattern is partial. That is exactly the kind of honesty Hermeneia needs.

After merge, the next implementation step should **not** be another motif tweak. It should be the larger shell/UI pass we just discovered from your walkthrough:

Next PR theme:

Active Screen Isolation \+ Reading Tools \+ Focus Mode Discipline

I’d structure the next prompt to Fable 5 around these concrete findings:

1\. Only the active screen should be visible.

   Stop the whole app from becoming one long scroll.

2\. Focus Mode should guide the next meaningful act,

   not merely dim the background.

3\. Reading Tools should replace Access Tools.

   Remove the wheelchair icon.

   Keep read-selection.

   Fix Text Large so it actually changes Reader text.

4\. Connections should be moved out of the main interpretive flow.

   Provider trust language needs neutral defaults, especially untested vs approved.

5\. Lineage must include reader/authorship history,

   not only rendered-report provenance.

For right now: **merge PR \#3**, then pull locally and restart so your browser reflects PR \#2 \+ PR \#3 before the next audit pass.

Information to inform hermeneia UI redesign– 

Yeah — now from the page context, the issue is very clear.

The app is **functionally rich but visually ungoverned**. It is showing too many modes at once. The strongest diagnosis:

Hermeneia currently presents the whole operating system at first glance,  
instead of presenting the next meaningful act.

What jumps out:

1. **Navigation is duplicated and contradictory**  
   You have top nav, stage nav, previous/next buttons, Guide/Constitution/Lineage buttons, and screen labels all visible together. The user sees “Corpus,” “Architect,” “Read,” “Critic,” “Screen 1,” “Screen 6,” etc. It feels like multiple control systems fighting.  
2. **The Working Thesis is too large for a persistent header**  
   It is important, but the full paragraph dominates the page. It should collapse into a “Current Question” card with an expand button.  
3. **Setup, Corpus, Guide, Lab, Review, Reports, Reader, Critic, Lineage, and Architect are all represented in the DOM at once**  
   Even if visually some are hidden, the page structure suggests the UI is carrying too many screens simultaneously. That creates the “clunky” feeling.  
4. **Provider connections are too prominent**  
   “Connections — Providers Loading provider status…” should not be in the main interpretive flow. That is system plumbing.  
5. **Corpus results are too raw**  
   The observation list is powerful, but visually it reads like a database dump: OBS IDs, counts, proposal stats, buttons, document labels, all repeated constantly.

## **The next design rule**

For the next pass, use this:

**Only one cognitive surface should be primary at a time.**

For the first screen, I’d make the default experience:

Current Question  
Primary Text / Reader  
Reading Trail  
Search

Everything else becomes secondary.

## **Immediate UI cleanup priorities**

### **P0 — Collapse the whole app shell**

Keep only:

Read  
Search  
Lab  
Reports  
Lineage

Move these behind “More”:

Corpus management  
Architect  
Critic  
Connections  
Constitution  
Guide  
Settings

### **P0 — Rename “Working Thesis” to “Current Question”**

Show one line:

What is the green light asking Gatsby to believe?

Then:

\[Show investigation frame\]

The thesis/purpose/lenses/falsifiability details should not dominate the screen.

### **P1 — Make Corpus a library, not the home**

Corpus management should look like:

Primary Text  
The Great Gatsby  
2,823 observations · 193 pages

Supporting Sources  
3 documents muted/commentary/reference

Not a giant administrative panel plus raw search results.

### **P1 — Split “Read” and “Search”**

The user should not see raw observation database results until they intentionally search.

Default:

Read the text  
Notice something  
Search a pattern

Not:

3,443 observations  
OBS-1  
OBS-3  
OBS-4  
...

## **The guiding phrase**

**Hermeneia needs to stop showing the machinery first.**

Not hide the evidence. Hide the machinery.

The interface should say:

Begin with the text.  
Keep what you notice.  
Ask a better question.  
Trace everything later.

That’s the UI spine.

## **Page 1 — Corpus Explorer audit**

### **What this page is trying to do**

This page is trying to be the **evidence base**:

manage documents  
define analysis scope  
search observations  
surface patterns  
select evidence for interpretation  
explain what the corpus is

That is legitimate. But it is currently trying to be **Corpus \+ Dashboard \+ Setup \+ Upload \+ Search \+ Guide \+ Pipeline Map** all at once.

---

## **First-time user likely reaction**

A new user probably thinks:

“Where do I start?”  
“Am I supposed to upload, search, edit the thesis, click Lab, or read?”  
“Why am I seeing thousands of observations?”  
“What is OBS-35?”  
“Why are commentary documents mixed into the novel?”

The problem is not that the information is wrong. The problem is that **everything has equal visual authority**.

---

## **What feels crowded/confusing**

### **1\. Corpus management and evidence search are merged**

Document roles, upload buttons, scope warnings, corpus list, observation results, and guide text are all on the same surface.

Those are different tasks.

Library management ≠ Evidence investigation

### **2\. The raw observation list feels like a database dump**

The OBS IDs, counts, proposal numbers, critic reports, bookmark buttons, and read-aloud buttons are valuable — but at first glance they overwhelm the actual passage.

The user’s eye should go to:

the passage  
where it came from  
why it matters

Instead it goes to machinery.

### **3\. Commentary is visually too close to primary evidence**

The commentary labels are present, which is good, but the commentary observations still sit in the same result stream as the primary text. For a first-time user, that risks source-boundary confusion.

Hermeneia knows the difference. The page does not make the difference strong enough.

### **4\. The “What is the Corpus?” guide is too low and too verbose**

It explains the page after the user has already been overwhelmed. It should become a short empty/help state or a collapsible “How to use this page.”

### **5\. “Screen 1 — Corpus Explorer” feels internal**

That sounds like an implementation label. The user-facing title should be simpler:

Evidence Library

or

Search the Text

depending on which mode this page is in.

---

## **What must stay**

These are constitutionally valuable:

Primary / commentary / reference roles  
In-scope vs excluded documents  
Warning when documents are excluded  
Exact observation text  
Source location: page / paragraph / sentence  
Pattern View  
Search/filter controls  
Immutable evidence language

Do not remove those. They are Hermeneia’s trust layer.

But they need better hierarchy.

---

## **What should collapse, move, rename, or defer**

### **Collapse**

Upload another document  
Supporting document upload  
Start from existing work  
Guide text  
Observation metadata counts

These should not be fully open by default.

### **Move**

Connections/providers → Settings or System  
Investigation Setup → Current Question card  
Guide/Constitution/Lineage → Trust/More menu

### **Rename**

Screen 1 — Corpus Explorer → Search the Text  
Analysis Scope → Sources in this investigation  
3,443 observations → 3,443 passages available  
OBS-\* → hide by default; show on expand  
Next: Interpretation Lab → Interpret selected passage →

### **Defer**

Detailed proposal counts  
Critic report counts per observation  
Bulk document role controls  
Full corpus administration

Those are expert tools, not first-glance tools.

---

## **Best next design move for this page**

Split it into two modes:

Sources  
Search

### **Sources mode**

For document management:

Primary Text  
The Great Gatsby  
2,823 passages · 193 pages · In scope

Supporting Sources  
Metaphor Essay  
620 passages · Commentary · In scope

Excluded  
Mandarin Essay  
Spanish Essay

### **Search mode**

For investigation:

Search the text  
\[ green light \]

Pattern View

Primary Text Results  
\- passage card  
\- passage card

Commentary Results  
Collapsed by default:  
“52 commentary passages available”

This preserves source-boundary integrity while making the user’s task obvious.

---

## **Page 1 verdict**

The Corpus page is powerful but currently **too administrative**. It should become:

**A calm evidence library where the user can search the text without feeling like they are operating a database.**

## **Bottom of Corpus page — audit**

The bottom confirms the real problem: **hidden screens are still readable/mentally present in the page flow.** Even though the user is “on Corpus,” the page context includes Lab, Review, Reports, Reader, Critic, Lineage, Architect, Guide, and Constitution content stacked below.

That means the interface is not just crowded at the top. It is structurally behaving like a long scroll of the entire app.

## **What this bottom section is trying to do**

It is trying to provide:

page education

next-step guidance

access to the full pipeline

fallback explanations for every screen

That is useful documentation, but it should not all live in the primary scroll.

## **What a first-time user likely feels**

Probably:

“Wait, am I still on Corpus?”

“Why am I seeing Lab, Review, Reports, Reader, Critic, Lineage, and Architect?”

“Are these sections part of one workflow or separate pages?”

“Am I supposed to scroll or click?”

The bottom creates **location uncertainty**.

The user loses the sense of place.

## **Main issue**

### **The app is using scroll as navigation**

That is the big one.

Instead of:

Corpus screen

the user sees:

Corpus

Lab

Review

Reports

Reader

Critic

Lineage

Architect

Guide

Constitution

This makes Hermeneia feel like a single-page documentation dump rather than a focused work environment.

## **What must stay**

These explanations are good:

What is the Corpus?

What is the Interpretation Lab?

What is Steward Review?

What are Reports?

What is the Critic?

What is the Lineage Explorer?

What is the Architect?

They are helpful, especially for accessibility and onboarding.

But they should become **contextual help panels**, not visible bottom-of-page sections.

## **What should change**

### **P0 — only render the active screen visibly**

When the user is on Corpus, the page should show:

Corpus header

Source scope

Search/pattern/results

Corpus help

It should not show the other screen content below.

If those other screens are technically in the DOM, they need `display:none`, `hidden`, or proper route isolation so they are not visually/semantically part of the page.

### **P0 — move “What is…” explanations into a right-side Help drawer**

Instead of long guide blocks below every screen:

\[? Help\]

opens:

What is the Corpus?

How to use it

Next meaningful action

That keeps the explanation available without turning the page into a manual.

### **P1 — remove “Screen 1 / Screen 2 / Screen 3” from user view**

Those labels are internal. They make the app feel like a wizard/debugger.

Use:

Corpus Explorer → Search the Text

Interpretation Lab → Interpret a Passage

Steward Review → Review Proposals

Architect Explorer → Structure the Argument

### **P1 — change next buttons from pipeline language to action language**

Current:

Next: Interpretation Lab →

Next: Steward Review →

Next: Architect →

Better:

Interpret selected passage →

Review generated proposal →

Build argument structure →

The user should know what action happens, not what internal stage comes next.

## **Constitutional read**

This bottom-of-page issue touches Article 3 and Article 5:

Earned Complexity:

The user is seeing every stage before needing it.

Provenance Over Procedure:

The page emphasizes pipeline procedure over the current act of investigation.

It is not dishonest in the same way the checkbox issue was, but it is cognitively noisy.

## **Page-bottom verdict**

The bottom of the page should not be a scrollable map of the whole system.

It should become:

Active screen

\+ contextual help

\+ one next meaningful action

The current version says:

“Here is the whole operating system.”

The next version should say:

“Here is the thing you are doing now.”

## **Page 2 — Interpretation Lab audit**

### **What this page is trying to do**

The Lab is trying to be the place where the user says:

Here is one observed passage.

Let several providers propose what it might mean.

Nothing is canonical yet.

That is a good purpose. The Lab should feel like a **proposal room**, not a control cockpit.

Right now it feels closer to a cockpit.

---

## **First-time user likely reaction**

A new user probably thinks:

“Did I select an observation?”

“What is Scope?”

“Why are there six AI providers here?”

“What does GPT vs Claude vs Meta mean for interpretation?”

“What is Evidence boundary?”

“What is response mode?”

“Am I allowed to click Generate yet?”

The Lab contains the right concepts, but the order makes the user meet system configuration before meaning.

---

## **What feels crowded/confusing**

### **1\. “Scope” appears before the selected evidence**

The page starts with source scope:

the-great-gatsby\_8s0co00z

Great Gatsby Metaphor Essay\_uzkw9cgq

Comparative interpretation

That matters, but the first thing the user needs is:

What passage am I interpreting?

The selected observation should be the hero card.

### **2\. Provider selection is too prominent**

This block:

GPT

Claude

Gemini

Grok

Meta

Local Model

4 providers ready

\+ Add providers

is power-user material. For first use, it makes the user think the task is choosing vendors rather than understanding the text.

Default should be:

Generate with recommended providers

\[Advanced: choose providers\]

### **3\. Evidence boundary is good but too technical**

This is constitutionally valuable:

primary source \+ commentary \+ muted docs

But it should read more like:

Evidence being used

Primary text: The Great Gatsby

Supporting commentary: 1 source

Excluded: 2 documents

Less math-symbol/corpus-id language.

### **4\. Response mode is good but needs hierarchy**

Interpretive / Triage / Skeptical is useful. But before a selected observation exists, these controls feel premature.

They should appear after the selected passage card, maybe under:

How should proposals respond?

### **5\. “Generate” is too bare**

Generate what?

Better:

Generate interpretation proposals

or:

Ask providers for interpretations

---

## **What must stay**

These are important:

Provider readiness

Evidence boundary

Response modes

Clear statement that proposals are not canonical

Steward Review as next step

Scope/source badges

The Lab should preserve the distinction:

proposal ≠ interpretation ≠ canonical understanding

That is core Hermeneia.

---

## **What should collapse, move, rename, or defer**

### **Collapse**

Provider checkboxes → Advanced

\+ Add providers → Connections/Settings

Detailed scope IDs → expandable “Evidence boundary”

### **Move**

Evidence boundary below selected passage

Provider settings below response mode

“What is the Lab?” into Help drawer

### **Rename**

Screen 2 — Interpretation Lab → Interpret a Passage

Select an observation from the corpus → Choose a passage in Search first

Generate → Generate interpretation proposals

Response mode → Proposal style

Evidence boundary → Evidence being used

### **Defer**

Manual provider matrix

Provider status details

Comparative provider tuning

Add providers from this screen

---

## **Ideal Lab layout**

The page should read top to bottom like this:

Interpret a Passage

Selected passage

\[quoted text\]

Source: The Great Gatsby · page X · paragraph Y

Why this passage matters / linked question

Evidence being used

Primary: The Great Gatsby

Supporting: 1 commentary source

Excluded: 2 muted docs

\[Show details\]

Proposal style

\[Interpretive\] \[Triage\] \[Skeptical\]

Providers

Recommended providers selected

\[Advanced\]

\[Generate interpretation proposals\]

That is much calmer.

---

## **Constitutional read**

The Lab is mostly constitutionally sound, but it violates **Earned Complexity** visually.

It gives the user:

provider mechanics

scope mechanics

response-mode mechanics

before grounding them in the selected evidence.

So the fix is hierarchy, not new logic.

---

## **Page 2 verdict**

The Lab should become:

**A quiet room where one passage is interpreted by proposal, with the evidence boundary visible but not dominant.**

The current Lab says:

“Configure providers and pipeline mode.”

The next Lab should say:

“Here is the passage. What might it mean, and who should propose?”

## **Page 3 — Steward Review audit**

### **What this page is trying to do**

This page is supposed to be the **human judgment chamber**:

AI proposes.

Human weighs.

Human establishes, contests, or marks uncertain.

Only stewarded understanding moves forward.

This is one of Hermeneia’s most important screens. It is where “human stewardship” becomes real.

Right now, though, the page is mixing **Steward Review** with **Pipeline Actions**, **Provider Selection**, **Profile Selection**, **Report Generation**, **Critic Launching**, and **Navigation**.

That makes the human judgment moment feel less sacred than it should.

---

## **First-time user likely reaction**

A new user likely thinks:

“Am I reviewing, generating, choosing providers, choosing profiles, or running reports?”

“What is speculative?”

“What does Establish mean?”

“What is the textarea for?”

“Why are Children’s / Executive / Spanish / Swahili profiles here before I’ve accepted an interpretation?”

The core action is buried.

The user should immediately understand:

“This proposal is not truth yet. My decision matters.”

That message is present in the help text, but not dominant in the layout.

---

## **What feels crowded/confusing**

### **1\. Pipeline Actions appear before human review**

The top of the page begins with provider/profile controls and buttons:

Run Artist

Run Critic

View Lineage

View Critic Reports

But those are downstream actions. They should not dominate before the user has stewarded proposals.

The first thing should be:

Proposal awaiting your judgment

### **2\. Provider/profile controls are in the wrong place**

Profiles like Children’s, Executive, Historical, Literary, Spanish, French, Swahili, Mandarin belong to report generation, not proposal review.

They should appear when the user chooses to render a report, not while deciding whether a candidate interpretation is sound.

### **3\. “Speculative” is accurate but not user-friendly enough**

`SPECULATIVE` is important, but the page should explain it inline:

Speculative — AI-proposed, not yet established

That one phrase would reduce confusion.

### **4\. The proposal card needs stronger hierarchy**

Current card contains:

provider

page

status

timestamp

ai-accepted

proposal text

source observation

textarea

Establish / Contest / Mark Uncertain

All valuable, but it needs visual grouping:

Candidate interpretation

Source passage

Your steward note

Your decision

### **5\. “Generated proposals will appear here” appears even when a proposal exists**

That sounds like an empty-state remnant. If proposals exist, it should not appear.

### **6\. Reports / Reader / Critic / Lineage / Architect sections still bleed below**

Again, active screen isolation is broken. Steward Review should not be followed by the content of five other screens in the same scroll.

---

## **What must stay**

These are constitutionally essential:

Speculative / established / contested / uncertain statuses

Source observation shown directly below proposal

Steward note textarea

Establish / Contest / Mark Uncertain buttons

Timestamp/status history

Clear statement that nothing becomes canonical without human decision

That is the soul of the page.

Do not remove human decision. Strengthen it.

---

## **What should collapse, move, rename, or defer**

### **Collapse**

Pipeline Actions bar

Provider checkboxes

Profile checkboxes

View Lineage / View Critic Reports buttons

These belong behind:

After review: Generate report

Advanced

### **Move**

Profile selection → Reports/Artist generation modal

Provider selection → Generate proposal/report modal

Run Critic → Reports or Critic screen after a report exists

View Lineage → report/proposal detail, not global top bar

### **Rename**

Screen 3 — Steward Review → Review Interpretations

SPECULATIVE → AI proposal — not established

Establish → Establish as interpretation

Contest → Contest this proposal

Mark Uncertain → Needs more review

Pipeline Actions → Next steps after review

### **Defer**

Multi-profile report rendering controls

Bulk provider/profile matrix

Critic/report launch from Review screen

These are powerful, but they should not pollute the first judgment moment.

---

## **Ideal Steward Review layout**

Review Interpretations

1 proposal awaiting your judgment

AI proposal — not established

Provider: GPT · Source: The Great Gatsby, p.1

Candidate interpretation

\[proposal text\]

Source passage

\[quoted observation\]

Your note

\[textarea\]

Why do you accept, contest, or hold this uncertain?

Decision

\[Establish as interpretation\]

\[Contest this proposal\]

\[Needs more review\]

After established:

\[Generate report from established interpretations\]

\[View lineage\]

That layout makes the human decision central.

---

## **Constitutional read**

This screen should embody:

Human stewardship

Provenance

History preservation

Observation before interpretation

It currently supports those structurally, but visually it gives too much priority to downstream machinery.

The fix is not new code architecture. It is ordering and hierarchy.

---

## **Page 3 verdict**

The Steward Review page is powerful, but it currently feels like an operator console.

It should feel like a **judgment desk**.

Current message:

“Choose providers/profiles and run pipeline actions.”

Better message:

“Here is a proposed interpretation. Read the evidence. Make a stewarded decision.”

## **Page 4 — Architect Explorer audit**

### **What this page is trying to do**

The Architect page is trying to bridge:

accepted interpretations

→ structured argument

→ blueprint

→ architect plan

→ auditable report instructions

That is extremely important. This is where Hermeneia stops being “AI interpretations” and becomes **argument architecture**.

But visually, this page currently feels like an advanced build tool dropped into the main user path.

---

## **First-time user likely reaction**

A new user probably thinks:

“What is a directive?”

“What is a blueprint?”

“Why am I generating this?”

“Do I need accepted interpretations first?”

“Should I import my own?”

“What happens if there are no blueprints yet?”

The page assumes the user already understands the pipeline. The help text explains it, but only after the form has already confronted them.

---

## **What feels crowded/confusing**

### **1\. “Generate from Directive” is too abstract**

A directive is internal language. The user likely understands:

Build an argument from my question

or:

Organize accepted interpretations

Better than:

Generate from Directive

### **2\. “Import Your Own” appears too equal to the main path**

Importing a blueprint is useful for expert users, but it should not have equal first-glance authority. The default user path is probably:

Use my accepted interpretations to build an argument.

Importing should be secondary/advanced.

### **3\. The page appears before the prerequisites are satisfied**

The context says:

No blueprints yet — generate one above.

But the question is: **Are there accepted interpretations yet?**

If there are none or only speculative proposals, the Architect should say:

Nothing is ready to structure yet.

Establish at least one interpretation in Review first.

Right now it invites blueprint generation even when the interpretive foundation may be thin.

### **4\. Provider selection appears again**

The provider dropdown belongs to generation settings, but first glance should not be:

choose GPT/Claude/Gemini/Grok/Meta/Local

It should be:

What argument should be built from your established interpretations?

Provider belongs under Advanced.

### **5\. The form labels are not self-explanatory enough**

Current:

Enter your research question or essay directive.

The Architect will synthesize a blueprint...

Better:

What argument are you trying to build?

Hermeneia will use only established interpretations as material.

That tells the user the boundary.

---

## **What must stay**

These are constitutionally valuable:

Blueprint generation

Import-your-own blueprint

Section-by-section claims

OBS-N references

Provider choice for synthesis if LLM-assisted

Statement that Architect Plan makes reports auditable

The Architect is essential. It just should not look like a raw internal tool.

---

## **What should collapse, move, rename, or defer**

### **Collapse**

Import Your Own

Provider dropdown

OBS-N reference field

Detailed section import fields

Behind:

Advanced blueprint options

### **Move**

Architect help text → contextual help drawer

Provider selection → Advanced generation settings

Import blueprint → Advanced/import tab

### **Rename**

Screen 6 — Architect Explorer → Build the Argument

Generate from Directive → Build from my question

Import Your Own → Import a blueprint

Enter your research question or essay directive → What argument are you trying to build?

Generate Blueprint → Build blueprint

No blueprints yet → No argument structure yet

### **Defer**

Full manual blueprint import UI

OBS-N advanced linking

Multi-provider Architect comparison

Blueprint library management

---

## **Ideal Architect layout**

Build the Argument

Ready material

1 established interpretation

3 speculative proposals not yet established

Current question

“What is the green light asking Gatsby to believe?”

Build an argument from established interpretations

\[textarea\]

What argument are you trying to build?

\[Build blueprint\]

Advanced

\- Choose provider

\- Import a blueprint

\- Add OBS-N references manually

No argument structure yet.

Establish interpretations in Review, then return here.

The key: it should show whether the foundation is ready.

---

## **Constitutional read**

This page touches **Provenance Over Procedure** and **Earned Complexity**.

The Architect should never feel like:

Generate a structure because this is the next stage.

It should feel like:

You have stewarded understanding. Now you may organize it.

That is a huge difference.

---

## **Page 4 verdict**

The Architect page has the right machinery but exposes it too early and too abstractly.

Current message:

“Generate from directive or import your own blueprint.”

Better message:

“Once you have established interpretations, Hermeneia can organize them into an auditable argument.”

This page should feel less like a prompt box and more like a **structure bench**: accepted material in, auditable argument out.

## **Page 5 — Reader / Close Reading Workspace audit**

This is the strongest page so far conceptually. The Reader is where Hermeneia finally feels like it knows what it is:

text

attention

highlights

questions

trail

machine observations

But it still has one major issue: **the machine layer is competing with the reading layer.**

---

## **What this page is trying to do**

The Reader is trying to let the user:

read the primary text

notice passages

highlight and annotate

ask questions

track human attention separately from machine extraction

compare human highlights to machine observations

That is excellent. This is where Hermeneia’s Witness layer is beginning to emerge.

---

## **First-time user likely reaction**

A new user probably understands the main idea faster here than on the other pages:

“I can read the text.”

“I can highlight things.”

“I can see what I’ve noticed.”

But then they may get pulled into confusion:

“Why are machine observations from pages 1 and 3 showing while I’m on page 2?”

“What does block:1 mean?”

“Why is the sidebar so dense?”

“Am I reading, inspecting, or auditing extraction?”

The Reader is close. It needs simplification, not rethinking.

---

## **What feels crowded/confusing**

### **1\. Machine Observations are too prominent**

The bottom/right section lists machine observations, including page 1 and page 3 content while the reader is on page 2\.

That is powerful for audit, but disruptive for reading.

Default user mode should be:

Text

Highlights

Questions

Machine observations should be behind:

Show extraction layer

### **2\. Block metadata should be expert-only**

This is useful:

block:1 · page:2:block:1

But it is not first-read material.

In universal/plain mode, show:

Page 2

Epigraph

Expert mode can show block IDs.

### **3\. Reading Trail is too dense**

The Reading Trail is excellent, but it currently shows many metrics at once:

pages read

last page

continue reading

saved highlights

statuses

questions

notes

clusters

coverage

roles

attention bars

recent highlights

recent questions

That is a lot.

Default should show only:

You saved 3 highlights

You raised 1 question

Continue reading

Recent highlights

Everything else under:

Details

You already have “Details ▾” — good. More should live behind it by default.

### **4\. Current Question is too long**

The question card works, but this question is a full thesis paragraph. It dominates.

Default display should clamp to 2 lines:

I want to understand what The Great Gatsby is actually arguing about aspiration…

\[Show full question\]

### **5\. Highlight Inspector is good but needs a simpler first state**

The instruction is good:

Select any passage in the text...

But the saved highlights and machine observations below it make the inspector feel like a second database panel.

A calmer structure:

Highlight Inspector

\- Selected passage editor, when selected

\- Saved highlights

\- Extraction layer collapsed

---

## **What must stay**

These are constitutionally valuable:

Primary/commentary document switch

Page navigation

Human highlights

Why this matters

Question this raises

Reading Trail

Human reading progress separate from machine coverage

Machine observations available for audit

Question card

Saved highlights preserved

Especially important:

“A map of attention, not a report card.”

Keep that. That is excellent language.

---

## **What should collapse, move, rename, or defer**

### **Collapse**

Machine Observations — This Page

block/page IDs

attention cluster details

highlights by role/status charts

long current question

### **Move**

Machine observations → Extraction layer / Audit drawer

Detailed trail metrics → Reading Trail details

Document role badges → small chips near document switcher

### **Rename**

Reader — Close Reading Workspace → Read the Text

Machine Observations — This Page → Extraction Layer

Highlight Inspector → Notes & Highlights

Reading Trail → Your Trail

### **Defer**

Full extraction audit display

Attention cluster visualizations

Machine/human coverage comparison

Page-block debugging

These are valuable but not first-glance.

---

## **Ideal Reader layout**

Read the Text

\[Primary\] The Great Gatsby

Page 2 / 193

Then wear the gold hat...

...

\[Prev\] \[Next\]

Right sidebar:

Your Trail

3 highlights · 1 question

Continue reading → page 3

Recent highlights

Your Question

“What is the green light asking Gatsby to believe?”

\[Edit\] \[Sharpen\]

Notes & Highlights

Select text to save a note or question.

Advanced

\[Show extraction layer\]

The Reader should feel like a reading room, not a lab instrument.

---

## **Constitutional read**

This page strongly supports:

Observation Before Interpretation

Every Interaction Preserves History

The User May Read Their Own File

Attention Stewardship

But it risks violating Earned Complexity by showing the extraction machinery too early.

The fix is simple:

Make the human reading layer default. Make the machine extraction layer inspectable.

Not hidden. Inspectable.

---

## **Page 5 verdict**

The Reader is the closest page to the soul of Hermeneia.

Current message:

“Read, but also inspect the machine extraction database.”

Better message:

“Read the text. Keep what you notice. The machine layer is available when you ask for it.”

This page should become the emotional anchor of the app.

## **Page 6 — Critic audit**

This page is conceptually important, but right now it feels like a **developer diagnostic screen**, not a user-facing fidelity audit.

The core idea is excellent:

OBSERVATION → INTERPRETATION → BLUEPRINT → ARCHITECT → ARTIST → CRITIC

That chain is Hermeneia’s trust promise. But the page currently opens with:

No critic reports yet.

Run: python3 scripts/herm critic OBS-N

Select a proposed interpretation to run the Critic.

That is useful for you as builder, but confusing for a normal user.

## **What this page is trying to do**

The Critic is trying to answer:

Did the final report preserve the evidence?

Did the Artist drop required concepts?

Did it add unsupported claims?

Can we trust the rendered narrative?

That is powerful. This is not “criticism” in the literary review sense. It is **fidelity checking**.

## **First-time user likely reaction**

A new user probably thinks:

“Why am I seeing a terminal command?”

“What is OBS-N?”

“Do I need to run Python?”

“What report is being audited?”

“Is this page broken because there are no critic reports?”

The page has strong architecture, but weak user-state messaging.

## **What feels crowded/confusing**

### **1\. The terminal command should not be first-class UI**

Run: python3 scripts/herm critic OBS-N

That belongs in developer mode, not the main Critic page.

In the app, the user should see a button:

Run fidelity audit

The CLI command can live under:

Developer details

### **2\. “No critic reports yet” needs a reason**

Better:

No reports are ready to audit yet.

Generate a report first, then run the Critic to check whether it preserved the evidence.

Or, if a report exists but no critic has run:

1 report is ready for audit.

\[Run fidelity audit\]

### **3\. The pipeline chain is good, but it should be contextual**

The chain is valuable, but it should highlight where the user is:

Observation → Interpretation → Blueprint → Report → Fidelity Audit

I would simplify the labels. “Architect” and “Artist” are meaningful internally, but for first-time users they sound like personas rather than stages.

### **4\. “Select a proposed interpretation” may be the wrong prerequisite**

The Critic audits rendered reports against the Architect Plan. So the page should orient around **reports**, not proposed interpretations.

Better:

Select a rendered report to audit.

If the Critic can also audit proposals later, that should be a different mode.

## **What must stay**

These should absolutely stay:

The provenance chain

Fidelity score

Dropped concepts

Unsupported additions

Warnings

Link back to source evidence

Statement that the Critic is not another AI opinion

That last one is big. It distinguishes Hermeneia from “ask another model if it agrees.”

## **What should collapse, move, rename, or defer**

### **Collapse**

CLI command

OBS-N references

technical run instructions

full explanatory text

### **Move**

python3 scripts/herm critic OBS-N → Developer details

“What is the Critic?” → Help drawer

pipeline explanation → compact audit chain

### **Rename**

Screen 4 — Critic → Fidelity Audit

No critic reports yet → No reports audited yet

Run Critic → Run fidelity audit

Critic reports → Fidelity reports

semantic fidelity score → Evidence preservation score

### **Defer**

CLI-driven critic workflow

OBS-level critic invocation

developer command hints

raw deterministic check details

Those are valuable, but not first-glance UI.

## **Ideal Critic layout**

Fidelity Audit

No reports audited yet.

The Critic checks whether a generated report preserved the evidence from the Architect Plan.

It does not add a new interpretation.

Ready to audit

1 rendered report available

\[Run fidelity audit\]

Audit chain

Observation → Interpretation → Blueprint → Report → Fidelity Audit

Developer details

python3 scripts/herm critic OBS-N

If no rendered report exists:

Fidelity Audit

Nothing is ready to audit yet.

First:

1\. Establish an interpretation in Review

2\. Build a blueprint in Architect

3\. Generate a report

4\. Return here to audit fidelity

\[Go to Review\]

## **Constitutional read**

This page strongly supports:

Provenance Over Polish

Every Claim Traceable

No Hidden Authority

Critique Without Confusion

But it currently violates **Earned Complexity** because it exposes CLI/operator language before the user has a report to audit.

## **Page 6 verdict**

The Critic page should not feel like a terminal wrapper.

Current message:

“Run this command after selecting an OBS.”

Better message:

“After a report exists, Hermeneia can audit whether the report preserved the evidence.”

The Critic should feel like a **fidelity chamber**, not a command-line instruction panel.

## **Page 7 — Guide / “How Hermeneia Works” audit**

This is one of the better pages conceptually. The writing is strong. The problem is not content quality — the problem is **density, repetition, and audience mismatch**.

This page reads like a manifesto plus architecture explainer plus constitutional proof all at once.

## **What this page is trying to do**

It is trying to explain:

Hermeneia is not a summarizer.

Hermeneia is a governed interpretation architecture.

Evidence becomes observations.

Observations become stewarded interpretations.

Interpretations become blueprints.

Blueprints become plans.

Plans become reports.

Reports get audited.

Everything remains traceable.

That is exactly the right story.

But the page currently gives the user the **whole theological/technical system in one pass**.

## **First-time user likely reaction**

A new user probably thinks:

“This sounds important.”

“I understand it is not just summarization.”

“But do I need to understand all of this before using it?”

“What is a constitutional substrate?”

“What is LILM?”

“What do SourceDocument, ArchitectPlan, ValidationReport mean?”

The page inspires trust, but it may also make the app feel harder than it is.

## **What feels crowded/confusing**

### **1\. The opening is too concept-heavy**

This line is accurate:

constitutional substrate for durable understanding

But it is not first-glance friendly.

For the first user-facing guide, lead with something plainer:

Hermeneia helps you read a source, preserve what you notice, test interpretations, and trace every final claim back to evidence.

Then let “constitutional substrate” appear under an advanced/expert explanation.

### **2\. “What category is this?” is strong but too early**

The category answer matters:

constitutional investigation architecture

But the user first needs:

What do I do here?

Why should I trust it?

How is this different from asking ChatGPT?

The category can come after the practical contrast.

### **3\. The LLM vs Constitutional Architecture diagram is important**

This is excellent:

LLM: Text → Text

Hermeneia: Corpus → Interpretation → Lineage

Keep it. This might be one of the clearest pieces on the page.

I would make this the hero section.

### **4\. The 01–07 pipeline is good but too verbose**

Each stage currently includes:

stage title

description

object names

invariant

Why this works

What prevents overreach

Technical note

That is valuable, but not all should be open by default.

Default should show:

Observe

Extract stable evidence from the source.

Evidence is permanent.

\[Why this works ▾\]

The rest collapses.

### **5\. Object model names should be expert-layer only**

These are useful:

SourceDocument

SourceExtraction

Observation

ProposedInterpretation

NarrativeBlueprint

ArchitectPlan

RenderedNarrative

ValidationReport

Finding

LineageGraph

But to a new user, they read like implementation tokens.

Show them under:

Developer / architecture terms

or a small “technical names” disclosure.

### **6\. “Read” as stage 05 is confusing**

The page uses:

05 Read

Render the plan into natural language via any provider.

But elsewhere “Reader” means close reading the text.

That is a terminology collision.

For the pipeline, this should probably be:

05 Render

or:

05 Express

Because “Read” already belongs to the human reading workspace.

That is a real UI vocabulary bug.

## **What must stay**

These are extremely valuable:

Not a document summarizer

LLMs are participants, not the system

Evidence is immutable

AI proposes; humans canonize

Reports are disposable

Lineage is permanent

The textbook / editions analogy

The LLM vs Hermeneia contrast

The constitutional principle at the end

Especially this:

Truth is constitutionally protected. Communication is continuously perfected.

That should stay. It is one of the clearest mission lines.

## **What should collapse, move, rename, or defer**

### **Collapse**

Why this works

What prevents overreach

Technical note

Object model names

LILM lineage paragraph

These should be expandable sections.

### **Move**

LILM lineage → advanced/history note

Technical notes → Developer mode

Read the Constitution CTA → bottom and maybe top secondary button

Object names → architecture glossary

### **Rename**

How Hermeneia Works → How Hermeneia Protects Understanding

01 Observe → Capture Evidence

02 Interpret → Propose Meaning

03 Organize → Build the Argument

04 Plan → Lock the Contract

05 Read → Render / Express

06 Audit → Check Fidelity

07 Trace → Trace Lineage

Most important rename: **Read → Render**.

### **Defer**

Hash IDs

database immutability details

regex/word-list fidelity details

content-derived object IDs

LILM history

Those are important, but not first-guide material.

## **Ideal Guide layout**

How Hermeneia Works

Hermeneia is not a summarizer.

It helps you build understanding from evidence, with every conclusion traceable back to the source.

Chatbot:

Text → Text

Hermeneia:

Source → Evidence → Interpretation → Argument → Report → Audit → Lineage

The basic rule:

Evidence is protected.

Meaning requires stewardship.

Reports can be rewritten.

Lineage remains permanent.

The path:

1\. Capture evidence

2\. Propose meaning

3\. Review and establish interpretations

4\. Build the argument

5\. Render the report

6\. Audit fidelity

7\. Trace every claim

\[Start reading\]

\[Search the corpus\]

\[Read the Constitution\]

\[Show technical architecture\]

That gives the user the whole idea without forcing them through the whole architecture.

## **Constitutional read**

This page is constitutionally strong, but it violates **Earned Complexity**.

It gives the user the whole system before they have earned the need for the whole system.

The fix is not to dumb it down. The fix is progressive disclosure:

Plain explanation first.

Constitutional meaning second.

Technical architecture third.

## **Page 7 verdict**

The Guide page contains some of Hermeneia’s best language, but it should become a **calm orientation page**, not a full architecture whitepaper.

Current message:

“Here is the entire constitutional substrate and object lifecycle.”

Better message:

“Hermeneia protects understanding by keeping evidence, interpretation, expression, audit, and lineage separate.”

Biggest actionable issue: rename pipeline stage **Read** to **Render** or **Express** to avoid collision with the Reader workspace.

## **Page 8 — Constitution audit**

This page is **stronger than the Guide** because its purpose is clearer. It is not trying to help the user operate the app. It is trying to declare the governing principles.

That said, it still has a first-glance problem: it reads like a legal/philosophical charter immediately, before giving the user a small map of what they are about to read.

## **What this page is trying to do**

The Constitution is trying to say:

Hermeneia is governed by principles.

Those principles are not branding.

They are enforced by data structures, UI boundaries, and workflow constraints.

That is exactly right.

This page should feel different from the rest of the app. It should feel like entering the foundation.

## **First-time user likely reaction**

A new user may think:

“This is serious.”

“This is not just an app.”

“I understand the values, but do I need to read all this now?”

“What does enforced by architecture mean?”

The content is good. The issue is that it asks for a lot of attention before orienting the reader.

## **What feels crowded/confusing**

### **1\. The page needs a short constitutional summary at the top**

Right now it jumps from title/quote into “Why Hermeneia Exists,” which is good writing, but the page would benefit from a compact “the whole constitution in one breath” card:

Hermeneia protects understanding by enforcing four separations:

Evidence from interpretation.

Interpretation from expression.

Proposal from stewardship.

Output from lineage.

That would help the reader understand the structure before reading P1–P8.

### **2\. “Constitutional substrate” is strong but heavy**

This phrase is accurate for you, and it should remain somewhere. But first-time users probably need the plain version first:

Hermeneia is infrastructure for preserving how understanding was formed.

Then the expert language can follow.

### **3\. Each principle has too much open text by default**

The repeated structure is excellent:

Principle

Why

How this is enforced

But all eight principles fully expanded makes the page long and dense.

Default should show:

P1 Observations Are Preserved

Evidence should survive changing interpretations.

\[Why\] \[How enforced\]

Then expand.

### **4\. “How this is enforced” is constitutionally important but should be collapsible**

This is the best part for technical credibility, but it is also the densest part. Keep it, but collapse it under an “Enforcement details” disclosure.

That preserves seriousness without making the page feel like documentation first.

### **5\. P8 has a possible tension**

P8 says the system exposes its own reasoning. That is excellent. But the current UI itself is exposing too much at once. This gives us a nice design test:

Expose mechanisms on request.

Do not force mechanisms into the user’s first act.

That distinction should probably become a UI principle later.

## **What must stay**

These are foundational and should not be softened away:

Observations Are Preserved

Interpretations Are Revisable

Provenance Is Required

Meaning Is Separated From Expression

AI Proposes; Humans Decide

Evaluation Is Deterministic

Understanding Is Cyclical

The System Exposes Its Own Reasoning

Also keep:

Truth is constitutionally protected. Communication is continuously perfected.

That is the spine.

## **What should collapse, move, rename, or defer**

### **Collapse**

Why

How this is enforced

Long enforcement paragraphs

Schema/API implementation claims

Default should show the principle and one sentence.

### **Move**

Full enforcement details → expanded technical section

“source code/database schema” implementation claim → bottom technical appendix

### **Rename lightly**

Most principle names are strong. I would not change much.

Possible softer display names:

P1 Observations Are Preserved → Evidence Is Preserved

P3 Provenance Is Required → Every Claim Needs a Source

P4 Meaning Is Separated From Expression → Meaning and Style Are Separate

P6 Evaluation Is Deterministic → Fidelity Checks Are Reproducible

But keep the formal names in expert/constitution mode.

### **Defer**

Hash ID explanation

foreign key details

specific file names like profile\_fidelity.py

database schema enforcement claims

Those can stay in expanded enforcement, not first view.

## **Ideal Constitution layout**

Hermeneia Constitution

“Truth is constitutionally protected.

Communication is continuously perfected.”

The constitution in brief:

Evidence is preserved.

Meaning is stewarded.

Expression is adaptable.

Lineage is permanent.

Principles

P1 Evidence is preserved

Source observations are immutable once recorded.

\[Why\] \[How enforced\]

P2 Interpretations are revisable

Understanding can deepen without rewriting the source record.

\[Why\] \[How enforced\]

P3 Every claim needs a source

Canonical claims must trace back to evidence.

\[Why\] \[How enforced\]

...

\[Show full technical enforcement appendix\]

## **Constitutional read**

Ironically, the Constitution page itself currently violates **Earned Complexity** a little.

Not because it is wrong. Because everything is expanded at once.

The better version should embody its own principle:

Make the foundation visible, but let the reader choose depth.

## **Page 8 verdict**

The Constitution is one of the best pages in the system. It has authority, seriousness, and a real governing framework.

Current message:

“Here is the full constitution and enforcement logic.”

Better message:

“Here is the governing law of Hermeneia. Read the summary now; inspect enforcement when you need to trust it.”

This page should feel like a charter with doors into technical proof, not a wall of proof all at once.

## **Bottom of Constitution page — audit**

The bottom confirms the Constitution page has the same structural issue as the Guide: it ends with useful navigation, but not enough **closure**.

Right now it closes with:

These principles are not aspirational — they are enforced by the architecture.

...

Where implementation diverges from principle, the principle is authoritative.

← Guide

Open Corpus

Inspect Lineage

That is strong, but the ending should feel more ceremonial and more actionable.

## **What the bottom is trying to do**

It is trying to say:

The Constitution governs the system.

The code is accountable to the principles.

Now return to work.

That is correct.

But visually, the bottom feels like the end of a documentation page, not the close of a charter.

## **What feels unfinished/confusing**

### **1\. The final principle is powerful but buried**

This line is extremely important:

Where implementation diverges from principle, the principle is authoritative.

That should not be just another paragraph. That is basically a supremacy clause.

It deserves a named closing block:

Supremacy Clause

Where implementation diverges from principle, the principle is authoritative.

That makes the Constitution feel real.

### **2\. The ending buttons are too generic**

Open Corpus

Inspect Lineage

Those are fine, but after reading the Constitution, the user needs a more meaningful next step:

Begin with evidence

Trace an existing claim

Return to the Guide

Those phrases connect the action to the Constitution.

### **3\. No “I understand” or “continue” moment**

Not every user needs this, but for onboarding, the Constitution could end with a soft acknowledgment:

I understand: evidence is preserved, meaning is stewarded, expression is adaptable, lineage is permanent.

\[Continue\]

Not a legal checkbox. More like a ceremonial transition back into work.

### **4\. It does not connect back to the current investigation**

The page could end with:

Return to your current investigation:

The Great Gatsby

Current question: ...

That would prevent the Constitution from feeling detached from the actual work.

## **What must stay**

Keep the final implementation-accountability paragraph. It is crucial.

Especially preserve:

These principles are not aspirational — they are enforced by the architecture.

and:

Where implementation diverges from principle, the principle is authoritative.

Those lines are the real bottom anchor.

## **Recommended bottom layout**

Supremacy Clause

These principles are not aspirational. They are enforced by the architecture.

Where implementation diverges from principle, the principle is authoritative.

The Constitution in one sentence:

Evidence is preserved. Meaning is stewarded. Expression is adaptable. Lineage is permanent.

Continue your investigation

Current text: The Great Gatsby

Current question: What is Gatsby asking us to believe about aspiration?

\[Begin with evidence\]

\[Trace a claim\]

\[Return to Guide\]

## **Verdict**

The bottom is conceptually strong but visually under-ceremonial.

Current message:

“That’s the end of the Constitution page.”

Better message:

“This is the law of the system. Now return to the work under that law.”

The Constitution should close like a charter, not like documentation.

## **Page 9 — Lineage Explorer audit**

This page is conceptually one of Hermeneia’s most important, but right now it is not yet earning its name visually because there is no rendered narrative or canonical finding to trace.

That means the page currently reads more like an empty-state explanation than an explorer.

## **What this page is trying to do**

The Lineage Explorer is supposed to answer:

How did this conclusion get here?

Its real job is to let the user walk backward:

Report

→ Architect Plan

→ Blueprint

→ Established Interpretation

→ Observation

→ Source Document

That is Hermeneia’s trust layer made visible.

## **First-time user likely reaction**

A new user probably thinks:

“Is this broken?”

“What is a rendered narrative?”

“What is a canonical Finding?”

“What is an E9 artifact?”

“Why are critic reports mentioned here if this is lineage?”

“What am I supposed to click?”

The empty state is accurate, but it uses too much internal language.

## **What feels confusing**

### **1\. “No rendered narratives yet” is technically true but not helpful enough**

Better:

Nothing is ready to trace yet.

Generate a report first, then Hermeneia can show how each claim connects back to the source.

That tells the user what is missing and why.

### **2\. “Canonical Findings” and “E9 artifacts” are expert language**

This line is probably correct internally:

No canonical Findings are present yet. Critic reports above are operational E9 artifacts...

But to a first-time user, it feels like a system log.

Plain version:

No final findings have been created yet.

Fidelity audits may exist separately, but claim-by-claim lineage appears here only after a report has findings to trace.

Expert version can preserve the E9 wording behind details.

### **3\. The page needs a visual chain even when empty**

Even before there is anything to inspect, the page should show the lineage promise:

Source Passage

→ Observation

→ Interpretation

→ Blueprint Claim

→ Report Claim

→ Finding

Right now, the concept is explained in paragraph form. It needs a map.

### **4\. “Every object in Hermeneia has a traceable origin” is strong**

Keep that. That sentence belongs here. This page is where it becomes product-visible.

### **5\. “Select a rendered narrative” is too narrow**

The user may want to trace from multiple entry points:

trace a report

trace an interpretation

trace an observation

trace a claim

Eventually, Lineage should not only be report-first. It should be claim-first, observation-first, and report-first.

For V1, report-first is fine, but the page should make that limitation clear.

## **What must stay**

These are essential:

report → plan → blueprint → interpretation → observation → source

exact source passage access

object-to-object provenance

distinction between operational critic reports and canonical findings

nothing asserted without evidence

The page is not optional. It is Hermeneia’s audit soul.

## **What should collapse, move, rename, or defer**

### **Collapse**

E9 artifact language

canonical Finding implementation language

technical empty-state distinctions

Put these under:

Developer details

### **Move**

“What is the Lineage Explorer?” → Help drawer or short explainer card

technical distinction between Critic artifacts and Findings → advanced note

### **Rename**

Screen 5 — Lineage Explorer → Trace Lineage

No rendered narratives yet → Nothing is ready to trace yet

canonical Findings → final findings / claim findings

operational E9 artifacts → fidelity audit records

### **Defer**

full graph visualization

multi-entry lineage tracing

finding-level lineage if reports do not exist yet

E9 terminology in normal UI

## **Ideal Lineage empty state**

Trace Lineage

Nothing is ready to trace yet.

Lineage appears after a report has been generated and audited.

Then Hermeneia can show how each claim connects back to the source.

The chain:

Source passage → Observation → Interpretation → Blueprint → Report → Finding

To create traceable lineage:

1\. Establish an interpretation in Review

2\. Build a blueprint in Architect

3\. Generate a report

4\. Run a fidelity audit

\[Go to Review\]

\[Go to Architect\]

\[Show developer details\]

## **Ideal Lineage populated state**

Trace Lineage

Report: Literary Profile · Gatsby aspiration analysis

Fidelity: 74%

Claims

1\. Gatsby performs wealth as a strategy of desire.

   Trace →

      Report paragraph 2

      Architect Plan required concept

      Blueprint claim 1

      Established interpretation

      OBS-35

      The Great Gatsby, p.2

\[Open source passage\]

\[View interpretation history\]

\[View audit finding\]

That would make the page immediately understandable.

## **Constitutional read**

This page strongly supports:

Provenance Is Required

The System Exposes Its Own Reasoning

Meaning Is Separated From Expression

But the current empty state violates **Earned Complexity** because it uses internal lifecycle vocabulary before the user has seen lineage work.

## **Page 9 verdict**

Lineage is one of the most important pages, but its empty state currently feels like a debug message.

Current message:

“No rendered narratives or canonical Findings exist; operational E9 artifacts are elsewhere.”

Better message:

“Nothing is ready to trace yet. Once a report exists, Hermeneia will show every claim’s path back to the source.”

This page should eventually feel like a **chain of custody viewer**, not a status screen.

Yes — that changes the framing.

I was treating Lineage too narrowly as **claim provenance after report generation**. But you’re right: this page is also where Hermeneia proves **authorship of attention**.

Not just:

How did this conclusion get here?

Also:

How did I get here as a reader?

That means Lineage has two kinds of history:

1\. Evidence lineage

Source → Observation → Interpretation → Blueprint → Report → Finding

2\. Reader lineage

Page read → Highlight → Note → Question → Revision → Steward decision

That is huge, because it means Hermeneia is not only proving the authorship of final claims. It is proving the authorship of **the interpretive journey**.

## **Revised Page 9 diagnosis**

The Lineage page should not be empty just because no rendered report exists.

Even with no report, the system already has reader-history lineage:

You read page 2\.

You highlighted the epigraph.

You wrote notes.

You asked a question.

You returned to the same passage.

You created an interpretive trail.

That is already lineage.

So the empty state is wrong, or at least incomplete.

## **Better model for this page**

Lineage should have tabs or modes:

Text Lineage

Shows where observations came from.

Reader Lineage

Shows your interaction history with the text.

Interpretation Lineage

Shows proposal → stewardship → established interpretation.

Report Lineage

Shows report claim → plan → blueprint → interpretation → observation.

For the current demo, the most valuable one is probably **Reader Lineage**, because you already have data:

3 highlights

1 question

3 notes

pages read

attention clusters

source roles

status markers

recent highlights

recent questions

That should not be buried only in the Reader sidebar. The Reader shows the living trail. Lineage should show the historical record.

## **Better empty/populated state**

Instead of:

No rendered narratives yet — run the Artist to generate the first.

It should say:

No reports have been generated yet.

Your reading lineage is already active:

3 highlights

1 question

3 notes

2 pages read

Report lineage will appear after a report is generated.

Then show:

Reader History

Page 2

\- Highlighted: “Then wear the gold hat…”

\- Note: “The novel opens with advice about performing wealth…”

\- Question: “Is the epigraph telling us Gatsby’s whole strategy in advance?”

## **Revised purpose statement**

The Lineage Explorer is not only a chain-of-custody viewer for final claims.

It is:

**A history of how understanding formed.**

That includes machine provenance, human attention, stewardship decisions, reports, audits, and revisions.

This is actually stronger than my first read. The page should prove:

This interpretation was not generated out of nowhere.

This reader noticed these passages.

This question emerged here.

This claim was later built from that trail.

That is authorship. Not in the shallow “I wrote this output” sense, but in the deeper sense:

**I can show the path by which this understanding became mine.**

## **Page 10 — Connections / Providers audit**

This page is powerful, but it absolutely confirms the biggest UI principle we’ve been circling:

**Hermeneia has system power exposed at user depth.**

Connections is not wrong. It is just way too close to the interpretive workspace.

## **What this page is trying to do**

The Connections page is trying to show:

which AI providers are available

which credentials are configured

which models are installed

which roles each provider can perform

whether providers have been calibrated

what local/Ollama models are ready

how credentials are stored

That is all important. This is Hermeneia’s **participant governance layer**.

But it should feel like a **settings/admin page**, not part of the reading flow.

## **First-time user likely reaction**

A new user likely thinks:

“Do I need to understand all this before reading?”

“What is Explorer vs Architect vs Artist vs Critic vs Witness?”

“Why are there tables for every provider?”

“What does approved/caution/rejected/untested mean?”

“Am I configuring an app or reading Gatsby?”

This page is not confusing because it lacks information. It is confusing because it contains **too much expert-level governance by default**.

## **What is constitutionally valuable here**

This page has real value. Do not remove the architecture behind it.

These must stay somewhere:

Provider readiness

Credential storage disclosure

Role suitability by provider

Calibration status

Override ability

Local model status

Ollama server/model readiness

No-key distinction for local models

Raw participant details for expert/debugging

The role matrix is actually excellent for Hermeneia because it says:

Not every model is equally trusted for every cognitive role.

That is a major governance idea.

But it should be progressive.

## **Main problems**

### **1\. Provider role tables are too expanded**

Every provider shows a full matrix:

Explorer

Architect

Artist

Critic

Witness

Suitability

Calibration

Run test

Override

Dropdown

Reason field

Apply

For six providers, this becomes an immediate wall.

Default should be summary cards only:

GPT

Ready · 4 recommended roles · uncalibrated

Claude

Ready · 4 recommended roles · uncalibrated

Meta

Ready locally · Artist allowed · Witness allowed

Local Model

Ollama running · qwen3:4b not pulled

Then:

\[Show role calibration\]

### **2\. “approved” appears selected even when calibration is untested**

This is a possible trust-language bug.

The table says:

Calibration: ○ untested

Dropdown: approved selected

Even if the dropdown is just the override selector default, visually it reads as contradiction:

untested but approved

That needs fixing. Default dropdown should probably be:

reset to untested

or blank:

Choose override…

This matters because calibration language is part of the trust contract.

### **3\. “Witness” is shown before the user knows what Witness means**

Witness is important, especially for reader/authorship lineage. But on this page, a first-time user sees it beside Explorer/Architect/Artist/Critic with no explanation.

Add a compact legend:

Roles:

Explorer — proposes observations/patterns

Architect — structures arguments

Artist — renders reports

Critic — checks fidelity

Witness — preserves user interaction/history

Even better: collapse roles until expanded.

### **4\. Credential copy is good but too technical at top**

This is good:

Keys are held in server memory only — never written to disk, forgotten when the server stops.

Keep it. It builds trust.

But visually it should be a small security notice, not competing with the page title.

### **5\. Local Model status is strong**

The Ollama details are actually one of the clearest parts:

Ollama server running

model pulled / not pulled

next command: ollama pull qwen3:4b

That is practical and good. The local model card is user-helpful.

But again, command details should be in “setup details,” not always expanded.

## **Rename recommendations**

Connections — Providers → Model Connections

Credential storage → Key storage

Suitability → Role fit

Calibration → Trust test

Override → Manual override

Participant raw details → Developer details

Run test → Test this role

Local Model → Custom Ollama model

## **Ideal layout**

Model Connections

Security

API keys are stored only in server memory and cleared when the server stops.

Ready

GPT

Ready · recommended for Explorer, Architect, Artist, Critic

\[Test connection\] \[Role calibration ▾\]

Claude

Ready · recommended for Explorer, Architect, Artist, Critic

\[Test connection\] \[Role calibration ▾\]

Meta / Ollama

Ready locally · no API key required

llama3.2:3b installed

\[Test connection\] \[Setup details ▾\]

Needs setup

Gemini

No key configured

\[Add key\]

Grok

No key configured

\[Add key\]

Custom Ollama model

Ollama running · qwen3:4b not pulled

\[Copy install command\] \[Test connection\]

Advanced

\[Show participant role matrix\]

\[Show raw provider details\]

## **Constitutional read**

This page supports a major Hermeneia principle:

AI providers are participants, not authorities.

That is excellent.

But the page currently risks overwhelming users because it exposes every participant-governance control before the user needs it.

Better principle:

Show readiness first. Show calibration on request. Show raw provider mechanics only in expert mode.

## **Page 10 verdict**

Connections should become a clean **Model Connections** settings page.

Current message:

“Here is every provider’s full role matrix, calibration controls, credentials, and raw details.”

Better message:

“These models are available. These are trusted for specific roles. Here is how to test or change that.”

The biggest bug to flag: **untested calibration paired with an “approved” selected dropdown**. That creates trust ambiguity and should be fixed before demo.

Yeah — accordion opened makes the issue sharper.

## **Connections accordion audit**

The advanced accordion content itself is good. It shows the truth plainly:

GPT: adapter installed, model configured, credential present

Claude: adapter installed, model configured, credential present

Gemini/Grok: adapter installed, no credential

Meta: Ollama running, model ready

Local Model: Ollama running, qwen3:4b not pulled

That is useful developer/system information.

But when opened, it proves two problems.

## **1\. The page has no containment**

After the advanced provider details, the app immediately falls into:

Investigation Setup

Corpus

Lab

Review

Reports

Reader

Critic

Lineage

Architect

Guide

Constitution

So the accordion is not the only thing expanding. The whole application is effectively one giant scroll document.

That is probably the single biggest structural UI bug in the app right now.

**Fix principle:**  
Only the active screen should be visually present. Everything else should be route-switched, tab-switched, or truly hidden.

## **2\. Advanced details are still too close to normal use**

The accordion content is correct, but it belongs behind stronger framing:

Advanced / Developer details

For debugging provider setup and model readiness.

Most readers do not need this to use Hermeneia.

Right now it opens into raw technical details, then immediately drops the user back into investigation setup. That makes the app feel unstable, like a dev console and product UI are sharing the same surface.

## **Trust-language issue confirmed**

This is still the most concrete bug on this page:

Calibration: ○ untested

Dropdown selected: approved

That is a trust contradiction. Even if “approved” is only the override choice, visually it reads as:

untested but approved

For Hermeneia, that matters. Calibration status is not decoration; it is part of the governance layer.

Better default:

Manual override: Choose…

Dropdown options:

Choose override…

Approve for this role

Use with caution

Reject for this role

Reset to untested

Do not default to “approved.”

## **Revised Page 10 implementation priorities**

### **P0 — Screen containment**

When Connections is open, only show Connections.

No Investigation Setup below it. No Corpus. No Lab. No Reader. No Guide. No Constitution.

This is bigger than Connections; it applies globally.

### **P0 — Fix calibration dropdown default**

Change selected default from `approved` to a neutral placeholder.

This is a governance/trust fix, not just UX polish.

### **P1 — Convert provider cards to summaries**

Default:

GPT

Ready · key present · 5 roles untested

\[Manage key\] \[Test connection\] \[Role details\]

Expanded:

Explorer recommended · untested

Architect recommended · untested

Artist recommended · untested

Critic recommended · untested

Witness allowed · untested

### **P1 — Move raw details into true developer drawer**

The raw details are valuable, but the drawer should feel intentionally separate:

Developer details

Adapter status, model IDs, environment credentials, Ollama readiness.

## **Verdict**

The opened accordion proves Hermeneia needs a **shell refactor** before a style pass.

Not “make the cards prettier.”

First:

Stop rendering the whole operating system in one scroll.

Then:

Make each page reveal one layer at a time.

For Fable 5, this is probably the next highest-value prompt: **Active Screen Isolation \+ Progressive Disclosure Spec.**

Perfect. Zooming in will help with the **actual human read** of the interface: spacing, visual weight, labels, button hierarchy, and whether the eye knows where to go.

As you show features, I’ll separate notes into three buckets:

Keep — the feature carries Hermeneia’s real value

Clarify — the feature is right but labeled/framed poorly

Hide/Move — the feature is too advanced or exposed too early

And I’ll keep a running special watch for:

authorship proof

reader history

source boundaries

provider trust language

screen containment

first-glance confusion

Go ahead — show me the first feature.

Yes — this is exactly the kind of thing that looks small but matters a lot.

The phrase:

All roles untested within Hermeneia.

is actually **good governance language**. It says Hermeneia is not pretending Grok is bad, good, safe, or unsafe in general. It is only saying:

Hermeneia has not yet validated this provider inside this system’s own interpretive roles.

That is the right standard.

But the UI under it immediately undermines that clarity because every role row says:

Suitability: untested

Calibration: ○ untested

Dropdown: approved

So the page says **untested** three times, then visually offers/appears to select **approved**.

That creates a trust contradiction.

## **What to keep**

Keep this kind of language:

All roles untested within Hermeneia.

Even better:

Grok is available as a provider, but no Hermeneia role has been validated yet.

That is clearer and less absolute.

## **What to fix**

The override dropdown should not default to `approved`.

It should default to a neutral placeholder:

Choose override…

Then options:

Approve for this role

Use with caution

Reject for this role

Reset to untested

And ideally the action should read:

Manual override

not just:

Override

## **Why this matters**

This is not cosmetic. Provider trust is part of Hermeneia’s constitution.

A model can be:

connected

available

recommended by design

untested in Hermeneia

approved after calibration

manually overridden by steward

Those are different statuses. The UI needs to keep them separate.

Ah — got it. I misunderstood what you were demonstrating.

That feature is **excellent**.

You’re showing that the accessibility tool is context-aware:

Highlight exact text → click Read → Hermeneia reads only that selection

That is not just accessibility polish. That supports Hermeneia’s core reading philosophy:

The user controls the unit of attention.

That means a reader can isolate one phrase, one sentence, or one confusing term without being forced into whole-page narration. For close reading, that matters a lot.

This should be marked as **Keep / Strengthen**, not hide.

Better UI framing might be:

Read Selection

Highlight text, then listen to only that passage.

And the popup/button should probably say:

Read selected text

instead of just:

Read

because the value is exactly what you said: it reads **just that part**.

Yes — that is exactly what **Focus Mode should become**.

Right now, based on the visible UI, Focus Mode says:

dim everything except the active screen

That is a decent accessibility idea, but for Hermeneia it should be more than visual dimming. It should become a **discipline mode**.

## **What Focus Mode should do**

Focus Mode should help the reader avoid this loop:

Corpus → Lab → Review → Architect → Reader → Critic → Lineage → Guide → Constitution → back to Corpus

and instead say:

Here is the next meaningful act.

Do this one thing.

Then move forward.

For Hermeneia, Focus Mode should probably mean:

**Hide everything except the current task, the current question, and the next valid step.**

## **Best version of Focus Mode**

When Focus is on, the UI should:

hide provider/settings panels unless needed

hide inactive screens completely

collapse the big thesis into one-line Current Question

hide Guide/Constitution/Connections buttons

show one primary action

show one next action

keep source/provenance visible

So on the Reader, Focus Mode becomes:

Read the Text

Current question:

What is Gatsby asking us to believe about aspiration?

Primary action:

Select a passage that matters.

Next step:

Save highlight or ask a question.

On Corpus/Search:

Search the Text

Primary action:

Search for a word, phrase, or motif.

Next step:

Choose one passage to interpret.

On Lab:

Interpret a Passage

Primary action:

Generate interpretation proposals for this selected passage.

Next step:

Review proposals.

## **The key design phrase**

**Focus Mode should reduce navigation, not just reduce brightness.**

Dimming is nice, but not enough. The real value is preventing endless cycling and overthinking.

I would define it in the spec like this:

Focus Mode constrains Hermeneia to one active cognitive task at a time. It hides nonessential navigation, advanced controls, and inactive pipeline surfaces while preserving the current question, source boundary, and next meaningful action.

## **This is actually constitutional**

This connects directly to **Attention Stewardship**.

Hermeneia should not only preserve attention after the fact through lineage. It should help protect attention while the user is working.

So yes: keep Focus Mode, but upgrade its meaning from:

visual dimming

to:

guided attention and next-step discipline

This should absolutely go into the next Fable 5 prompt.

toggle text size does nothing

Yep — that is a real bug, and it’s worth logging as **accessibility P0/P1**, not cosmetic.

The button says:

Aa

Text

Large

and its title says:

Increase reading text size

But if toggling it doesn’t change the visible reading text, then the UI is making an accessibility promise it does not fulfill.

## **What it should do**

At minimum, it should affect the **Reader text blocks**:

Page 2 text

epigraph

main source passage

selected passage popup

possibly saved highlights

It should probably **not** enlarge every control/table/provider matrix. The purpose is readability of the source, not making the whole admin UI huge.

## **Likely intended behavior**

The toggle should cycle something like:

Normal → Large → Extra Large → Normal

or:

Large text: Off / On

Right now the label suggests it has entered “Large,” but there’s no observable effect.

## **Bug note for the working document**

Bug: Access Tools “Text Large” toggle appears to change state but does not visibly change reader text size.

Impact: Accessibility affordance is nonfunctional. This weakens trust in the Access Tools dock and harms users who rely on larger text for close reading.

Expected: Toggling text size should visibly increase the source text / Reader text blocks, ideally without enlarging the entire system UI.

Suggested fix: Bind the toggle to a persistent class on the app or Reader container, e.g. \`reader-large-text\`, and apply font-size/line-height changes to source text, selected passages, and reading panels.

This one belongs beside Focus Mode and Read Selection as an Access Tools pass.

Agreed. The ♿ icon is technically recognizable, but it frames the whole dock as “disability tools,” which is narrower and heavier than what Hermeneia is doing.

This dock is really about **attention support**, not only accessibility.

Better labels/icons:

Access Tools → Reading Tools

♿ Access → ◐ Focus

♿ Access → Aa Tools

♿ Access → ✦ Assist

♿ Access → ☰ Reading

My strongest recommendation:

Reading Tools

icon: Aa

or

Attention Tools

icon: ◐

Because the features are:

Read selected text

Stop reading

Focus mode

Text size

That is not “handicap.” That is **reader agency**.

Bug/UX note to keep:

UX issue: Accessibility dock uses ♿ icon, which implies disability-only affordances. Replace with a neutral reading/attention icon such as “Aa,” “◐,” or “✦” and rename dock from “Access Tools” to “Reading Tools” or “Attention Tools.”

For Hermeneia, I’d choose **Attention Tools** if Focus Mode becomes guided next-step discipline. If it stays mostly text-to-speech and font sizing, choose **Reading Tools**.

