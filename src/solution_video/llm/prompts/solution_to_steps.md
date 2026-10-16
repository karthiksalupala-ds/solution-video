# Solution to steps

Return one JSON object only. Use only the supplied input. Do not invent facts, sources, companies, values, or formulas.

Create 2 to 5 steps. Every step must include at least one short, machine-evaluable arithmetic equality (exactly one `=`) and show its computed result. Do not use generic formulas as a substitute for calculations. The first evaluable step must use only numeric operands stated in the question or standard constants: 18/5, 5/18, 100, 60, 3600, 1000, or 1 whole unit. Later steps may use results established in earlier steps. Keep each line under 90 characters.

For time-and-work questions, calculate each person's one-day work rate on its own line before combining rates. For data-interpretation questions, calculate each part's value or rate separately before combining or comparing them. Do not use a combined value until its component calculations have been shown.

End the calculation sequence with a genuine machine-evaluable computation whose result is the numeric final answer (units may be shown). Do not use filler equalities such as `165 = 165`. Do not copy the supplied final answer if the question's calculations do not produce it.

Keep `display` (on-screen) and `speech` (spoken) separate. Apply the supplied speech-language configuration to every step speech and to any tip, answer, and outro/CTA speech. State the actual values and results in speech. Make operators and units speakable: say `x` as “times”, `/` as “divided by”, `%` as “percent”, and `km/h` as “kilometres per hour”; do not read raw calculation symbols aloud. Include `answer` as an object with `display` exactly equal to the supplied final answer, a spoken `speech` line that states the answer and correct option, and `correct_option` exactly equal to the supplied option letter. If present, `tip` must be an object with both `display` and `speech`; never return a bare string.

Never include a `source` field. Do not alter the question, options, or final answer.

Valid example (use its structure and calculation detail; replace every value and line with values derived from the current input):
```json
{
  "steps": [
    {
      "label": "Step 1: Add train and platform lengths",
      "lines": ["150 + 250 = 400 m"],
      "speech": "First, one hundred fifty metres plus two hundred fifty metres equals four hundred metres."
    },
    {
      "label": "Step 2: Find speed in meters per second",
      "lines": ["400 / 20 = 20 m/s"],
      "speech": "Next, four hundred metres divided by twenty seconds is twenty metres per second."
    },
    {
      "label": "Step 3: Convert to kilometres per hour",
      "lines": ["20 x 18/5 = 72 km/h"],
      "speech": "Twenty metres per second times eighteen divided by five is seventy-two kilometres per hour."
    }
  ],
  "answer": {
    "display": "72 km/h",
    "speech": "So the answer is seventy-two kilometres per hour, option A.",
    "correct_option": "A"
  },
  "tip": {
    "display": "Convert m/s to km/h by multiplying by 18/5",
    "speech": "To convert metres per second to kilometres per hour, multiply by eighteen divided by five."
  }
}
```
