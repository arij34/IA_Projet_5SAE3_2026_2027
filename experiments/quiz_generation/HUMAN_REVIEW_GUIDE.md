# Human review guide — saved quiz outputs A/B/C

Freelancy academic project, IA for Software Engineering. This guide supports an **independent human review** of the 90 saved questions in `results/final_v2_run.json` (conditions A `quiz-baseline-v0`, B `quiz-gen-v1`, C `quiz-objective-v2`; 6 cases × 5 questions each). Ratings are **not completed** until a person fills them in.

## Files

| File | Role |
|---|---|
| `results/independent_human_review_v2.json` | The worksheet you edit (90 records, all `UNREVIEWED`). |
| `human_review.py` | Creates (`init`), checks (`validate`) and counts (`summary`) the worksheet. Offline; no model or network. |
| `test_human_review.py` | Offline tests of the validator. |
| `results/offline_quality_review_v1.tsv` | AI-assisted first pass. **Do not read it before finishing**, so your ratings stay independent. |
| `results/independent_human_review_template_v1.json` | Earlier blank template, kept unchanged. Superseded by v2 (no record IDs, no rating definitions, no `NOT_ASSESSABLE`, no second-review flag, no source hashes). Do not use it. |

The saved run, dataset and earlier artifacts are never modified. The worksheet stores the SHA-256 of the run and dataset, and a hash per question; `validate` fails if the displayed question differs from the saved output.

## Procedure

1. Open `independent_human_review_v2.json`. Records are ordered by `case_id`, then condition, then question, so A, B and C for one case appear together.
2. For each record read `case_context` (objective, rubric, reference URLs) and `question` (text, choices, marked answer, explanation). Check disputed claims against the official reference, or by running the code.
3. Edit only the `human_review` object. Set every rating, `second_review.flag` (`true`/`false`), `reviewer_id`, `reviewed_on` (`YYYY-MM-DD`), then `status` to `"REVIEWED"`. Leave `null`/`UNREVIEWED` for records you have not finished; they are never counted.
4. Run `validate` regularly. Fix reported errors.
5. Compare conditions per case: for each `case_id`, apply the same standard to A, B and C. Questions differ between conditions, so compare ratings and defects, not identical items. The condition labels are visible; be aware this can bias judgement. Do not rate a question higher because the prompt was longer or richer.
6. When all 90 are `REVIEWED`, run `validate --require-complete` (exit code 0 only when complete), then `summary`.

```powershell
.\.venv\Scripts\python.exe -m experiments.quiz_generation.human_review validate
.\.venv\Scripts\python.exe -m experiments.quiz_generation.human_review validate --require-complete
.\.venv\Scripts\python.exe -m experiments.quiz_generation.human_review summary
.\.venv\Scripts\python.exe -m unittest experiments.quiz_generation.test_human_review -v
```

`init` only creates a missing worksheet and refuses to overwrite an existing one. Back up your worksheet outside Git operations before experimenting.

## Rubric

Every criterion must be rated; `NOT_ASSESSABLE` means you cannot judge it from the question, reference and your own verification (never use it as a default).

| Criterion | Values | Meaning |
|---|---|---|
| `technical` | `CORRECT` / `INCORRECT` / `NOT_ASSESSABLE` | Is the marked answer actually correct? Objective; verify against docs or execution. `INCORRECT` includes a question with no correct option. |
| `relevance` | `RELEVANT` / `PARTIAL` / `IRRELEVANT` / `NOT_ASSESSABLE` | Does it assess the case learning objective and topic? |
| `difficulty` | `APPROPRIATE` / `TOO_EASY` / `TOO_HARD` / `NOT_ASSESSABLE` | Fit with the case `difficulty_label`. Subjective. |
| `clarity` | `CLEAR` / `MINOR_ISSUE` / `AMBIGUOUS` / `NOT_ASSESSABLE` | Precise, understandable wording. `AMBIGUOUS` = a reasonable reader could interpret the question differently. Subjective. |
| `uniqueness` | `EXACTLY_ONE` / `MULTIPLE` / `NONE` / `NOT_ASSESSABLE` | Number of defensible correct options. |
| `distractors` | `PLAUSIBLE_WRONG` / `WEAK` / `FLAWED` / `NOT_ASSESSABLE` | Wrong options are tempting but incorrect (`PLAUSIBLE_WRONG`); trivially implausible (`WEAK`); or actually correct/misleading through a defect (`FLAWED`). |
| `explanation` | `ACCURATE` / `PARTIAL` / `INACCURATE` / `NOT_ASSESSABLE` | Does the explanation correctly justify the marked answer? If no explanation exists, use `NOT_ASSESSABLE`. |

Rate the marked answer and explanation as saved; do not silently correct them. Structural validity (the `machine_validation` block) shows the output parsed; it says nothing about truth.

### Evidence notes

A **critical defect** is `technical = INCORRECT`, `uniqueness = MULTIPLE` or `NONE`, or `explanation = INACCURATE`. These (and `technical = NOT_ASSESSABLE`) require `evidence` (at least 15 characters, e.g. the documentation passage or executed result) and a `defect` description. `recommended_correction` is optional.

### Disputed or uncertain items

Set `second_review.flag` to `true` and give a `reason` when you are unsure or the question is disputable. Flagged records still count as reviewed but are listed in `summary` for a second reviewer.

### Reviewer identity

`reviewer_id` is only 2–8 alphanumeric characters (initials or a pseudonym); no other personal data is needed. `reviewed_on` records the date for auditability.

## What this does and does not establish

- Reviewed counts are descriptive; with one run, one output per case/condition and 30 questions per condition, they are not statistically significant and do not generalize.
- `summary` counts only `REVIEWED` records; it prints `reviewed`/`records` so partial reviews cannot pass as complete.
- No LLM is used to judge. Reviewer agreement with the AI-assisted TSV is not computed here and would be a separate, post-review step.
