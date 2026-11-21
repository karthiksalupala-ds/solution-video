# Solution to steps

Return one JSON object only. Use only the supplied input. Do not invent facts, sources, companies, values, or formulas.

Create 2 to 5 steps. Never round numbers: use exact fractions and integers, not decimal approximations, unless the question itself supplies decimal values. Every step must include at least one short, machine-evaluable arithmetic equality (exactly one `=`) and show its exact result. Do not use generic formulas as a substitute for calculations. The first evaluable step must use only numeric operands stated in the question or standard constants: 18/5, 5/18, 100, 60, 3600, 1000, or 1 whole unit. Later steps may use exact results established in earlier steps. Keep each line under 90 characters.

For time-and-work questions, calculate each person's one-day work rate on its own line before combining rates. Preserve exact fractions throughout; for example, show `1/12 = 1/12 work/day` and `1/24 = 1/24 work/day`, then combine with exact common-denominator steps such as `1/12 + 1/24 = 2/24 + 1/24`, `2/24 + 1/24 = 3/24`, and `3/24 = 1/8`. Finish with `1 / (1/8) = 8 days`. For data-interpretation questions, calculate each part's value or rate separately before combining or comparing them. Do not use a combined value until its component calculations have been shown.

End the calculation sequence with a genuine machine-evaluable computation whose result is the numeric final answer (units may be shown). Do not use filler equalities such as `165 = 165`. Do not copy the supplied final answer if the question's calculations do not produce it.

Keep `display` (on-screen) and `speech` (spoken) separate. Apply the supplied speech-language configuration to every step speech and to any tip, answer, and outro/CTA speech. State the actual values and results in speech. Make operators and units speakable: say `x` as “times”, `/` as “divided by”, `%` as “percent”, and `km/h` as “kilometres per hour”; do not read raw calculation symbols aloud. Include `answer` as an object with `display` exactly equal to the supplied final answer, a spoken `speech` line that states the answer and correct option, and `correct_option` exactly equal to the supplied option letter. If present, `tip` must be an object with both `display` and `speech`; never return a bare string.

Include a non-empty `intro_speech` string: one short, friendly opening that follows the spoken day/topic title. Do not reveal the final answer in the opening. The question and options are shown on screen, so do not read or repeat them in any speech field.

Voice personality: sound like a friendly tutor explaining the idea to one learner, not an answer key or a presenter reading notes. Start with the meaning of the step in everyday language; briefly explain why the operation fits and what its result means; then weave in the relevant values and result. Use contractions and natural transitions such as “Right”, “So”, or “Now” when they fit; vary sentence rhythm and do not force every step into the same template. A brief rhetorical question is fine when it genuinely helps explain the idea, but avoid scripted audience interaction, filler, jokes, and repeated stock openings. Do not read each formula line word-for-word. Keep the explanation factual, concise, and complete; preserve the real values, units, and reasoning. Use one to three short sentences per step as needed, and end with a warm, clear answer.

Never include a `source` field. Do not alter the question, options, or final answer.

Valid example (use its structure and calculation detail; replace every value and line with values derived from the current input):
```json
{
  "intro_speech": "Okay, let's work this out together.",
  "steps": [
    {
      "label": "Step 1: Add train and platform lengths",
      "lines": ["150 + 250 = 400 m"],
      "speech": "Right, the train has to clear the whole platform, not just get to the end. So we add its one hundred fifty metres to the platform's two hundred fifty metres: four hundred metres altogether."
    },
    {
      "label": "Step 2: Find speed in meters per second",
      "lines": ["400 / 20 = 20 m/s"],
      "speech": "Those four hundred metres take twenty seconds. In other words, the train covers twenty metres each second."
    },
    {
      "label": "Step 3: Convert to kilometres per hour",
      "lines": ["20 x 18/5 = 72 km/h"],
      "speech": "They want kilometres per hour, so let's switch units. Multiply twenty by eighteen over five, and we get seventy-two kilometres per hour."
    }
  ],
  "answer": {
    "display": "72 km/h",
    "speech": "So there we go: seventy-two kilometres per hour, option A.",
    "correct_option": "A"
  },
  "tip": {
    "display": "Convert m/s to km/h by multiplying by 18/5",
    "speech": "To convert metres per second to kilometres per hour, multiply by eighteen divided by five."
  }
}
```
