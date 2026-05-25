# Prompt Structure For Improving Turf Intelligence

This guide is for working on the app’s AI behavior without turning prompt edits into random trial-and-error.

Use it when you want to improve:

- answer quality
- answer consistency
- tone and structure
- topic coverage
- clarification behavior
- safe handling of uncertainty

Do not use prompt edits as the first fix for missing data, routing bugs, or broken retrieval.

## Where Prompt Logic Lives

The main prompt file is [prompts.py](/Users/christiancrossmock/Desktop/turf-ai/prompts.py).

Current structure:

- `BASE_PROMPT`
  - role definition
  - response philosophy
  - formatting rules
  - hard safety boundaries
  - confidence and contradiction rules
- `KNOWLEDGE_SUPPLEMENT`
  - core reference facts the assistant can lean on
- `FEW_SHOT_EXAMPLES`
  - demonstrations of reasoning and answer style
- topic-specific prompt modules
  - disease
  - herbicide
  - insect
  - irrigation
  - fertilizer
  - cultural
  - equipment
  - diagnostics
- `build_system_prompt(question_topic, product_need)`
  - assembles the final system prompt based on request type

## How To Decide Whether Prompt Work Is The Right Fix

Prompt changes are a good fit when the app:

- answers with the wrong level of detail
- skips clarifying questions when ambiguity is obvious
- sounds generic or weak even with good context
- fails to separate diagnosis from recommendation
- overstates certainty
- gives turf-correct facts in an unhelpful format

Prompt changes are not the right first fix when the app:

- lacks the needed source material
- fails to retrieve the right documents
- confuses product facts because the KB is incomplete
- ignores course profile state because controller logic is wrong
- gives unsafe output because validators are too weak

In those cases, change the system layer first, then tighten prompts after.

## Recommended Prompt Stack

When improving prompts, keep this order:

1. `Role`
   - who the assistant is and what expertise it has
2. `Behavior Standard`
   - what a strong answer looks like
3. `Safety Boundaries`
   - what it must never guess, overstate, or recommend
4. `Reasoning Pattern`
   - how it should think through ambiguity, evidence, and next actions
5. `Topic Rules`
   - domain-specific logic for the current question type
6. `Formatting Rules`
   - how the final answer should be shaped for users
7. `Examples`
   - a few high-signal examples, only where needed

This repo already roughly follows that model. Improvements should usually strengthen one layer rather than dumping more text into every layer.

## Prompt Writing Rules For This App

When editing prompts in this codebase:

- prefer short, enforceable instructions over long motivational prose
- describe output behavior, not hidden chain-of-thought
- tell the model what to do when evidence is incomplete
- separate “identify”, “verify”, and “recommend”
- prefer “say you are unsure” over invented specifics
- keep label, registration, and rate safety rules explicit
- avoid duplicate rules repeated across many prompt blocks unless repetition is intentional

Good instruction style:

```text
Lead with the practical bottom line. If evidence is incomplete, name the top 2-3 possibilities and ask for the deciding field check before recommending treatment.
```

Weaker instruction style:

```text
Be smart, comprehensive, helpful, safe, practical, detailed, and insightful at all times.
```

## Prompt Template For New Functional Improvements

Use this template when introducing a new prompt section or revising an existing one:

```text
PURPOSE:
Help the assistant perform better for [specific use case].

WHEN TO APPLY:
Use for [question type, route, mode, or classifier result].

ANSWER STANDARD:
- Lead with [bottom line / diagnosis / action plan]
- Include [specific evidence or constraints]
- Distinguish between [diagnosis vs treatment / known vs inferred]
- If confidence is low, [ask clarifying question / present top possibilities]

DO:
- [behavior 1]
- [behavior 2]
- [behavior 3]

DO NOT:
- [failure mode 1]
- [failure mode 2]
- [failure mode 3]

ESCALATE UNCERTAINTY WHEN:
- [condition 1]
- [condition 2]

FORMAT:
- [short structure for final answer]
```

## Suggested Working Prompt For AI-Assisted App Improvements

If you want another coding/AI assistant to help improve this app, use this prompt structure:

```text
You are helping improve Turf Intelligence, a Flask-based turf management assistant.

Your job is to improve functionality without breaking answer quality, safety, or routing.

Project expectations:
- Prefer fixing the correct layer instead of defaulting to prompt edits.
- Treat verified product answers as a higher-trust path than generic generation.
- Preserve grounding, validation, and safety behavior.
- Match existing architecture and keep changes narrow.
- Add or update tests/evals when behavior changes.

Before changing anything:
1. Identify the user-visible problem.
2. Identify the most likely layer responsible:
   - UI/templates
   - route/controller logic
   - retrieval/search
   - verified KB / structured knowledge
   - prompts
   - validation/safety/grounding
3. Explain why that layer is the right place to fix it.

When working on prompts:
- Improve specificity, uncertainty handling, and answer structure.
- Do not use prompts to compensate for missing facts in the KB.
- Do not relax safety rules around rates, labels, or product certainty.
- Prefer concise, testable prompt edits.

When finished:
- summarize what changed
- note any risks or assumptions
- list the tests/evals run or still needed
```

## Suggested Task Brief Template

Use this for individual improvement tasks:

```text
Goal:
Improve [feature or behavior].

Current problem:
[describe the failure clearly]

Expected behavior:
[describe the user-visible outcome]

Likely layer:
[prompt / retrieval / verified kb / validation / ui / route logic]

Constraints:
- Keep existing safety rules
- Do not fabricate product facts
- Preserve verified KB priority when applicable
- Keep changes minimal and readable

Validation:
- Run [specific test or eval]
- Manually verify [specific scenario]
```

## Good Targets For Prompt Improvements In This App

Prompt work is likely useful for:

- better clarification when diagnosis details are thin
- more consistent “bottom line first” answers
- cleaner separation between likely cause and action plan
- more consistent communication of uncertainty
- preventing overlong answers to simple questions
- improving topic-specific answer shape after retrieval is already good

## Good Targets For Non-Prompt Improvements

Choose another layer first for:

- missing product labels or structured fields
- low-quality retrieval ranking
- wrong topic classification
- broken image handling
- account/session bugs
- feedback/admin workflow issues
- readiness and deployment checks

## Practical Workflow

Use this loop when improving functionality:

1. Reproduce the weak behavior with a real prompt or route.
2. Decide whether the failure is prompt-related or system-related.
3. Make the smallest plausible change.
4. Run the nearest regression test or eval.
5. Re-test the original scenario.
6. Check one adjacent scenario to make sure the fix did not overfit.

## Related Files

- [prompts.py](/Users/christiancrossmock/Desktop/turf-ai/prompts.py)
- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py)
- [verified_kb.py](/Users/christiancrossmock/Desktop/turf-ai/verified_kb.py)
- [answer_validator.py](/Users/christiancrossmock/Desktop/turf-ai/answer_validator.py)
- [answer_grounding.py](/Users/christiancrossmock/Desktop/turf-ai/answer_grounding.py)
- [safety_gate.py](/Users/christiancrossmock/Desktop/turf-ai/safety_gate.py)
- [scripts/run_demo_prompt_check.py](/Users/christiancrossmock/Desktop/turf-ai/scripts/run_demo_prompt_check.py)
