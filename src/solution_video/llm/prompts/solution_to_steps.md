# Solution to steps

Return one JSON object only. Use only the supplied input. Do not invent facts, sources, companies, values, or formulas.

Create 2 to 5 steps. Every step must include at least one short, machine-evaluable arithmetic equality (exactly one `=`) using the actual numeric values from the question, and show the computed result. Do not use generic formulas as a substitute for calculations. For example, show `150 + 250 = 400 m`, then `400 / 20 = 20 m/s`, then `20 x 18/5 = 72 km/h` when those are the supplied values. Keep each line under 90 characters. Step speech must naturally say the actual input values and the result aloud in Tanglish written in Latin script; do not read raw mathematical symbols.

End the calculation sequence with a machine-evaluable equality whose result is the numeric final answer (units may be shown). Do not copy the supplied final answer if the question's calculations do not produce it. Include `answer` as an object with `display` exactly equal to the supplied final answer, a natural spoken `speech` line that says that answer and its correct option (for example, “So the answer is 72 kilometres per hour, option A”), and `correct_option` exactly equal to the supplied option letter. If present, `tip` must be an object with a `display` field and optional `speech` field; never return a bare string.

Never include a `source` field. Do not alter the question, options, or final answer.

Valid example (use its structure and calculation detail; replace every value and line with values derived from the current input):
```json
{
  "steps": [
    {
      "label": "Step 1: Add train and platform lengths",
      "lines": ["150 + 250 = 400 m"],
      "speech": "Munduga train length 150 meters ki platform length 250 meters add chesthe 400 meters vastundi."
    },
    {
      "label": "Step 2: Find speed in meters per second",
      "lines": ["400 / 20 = 20 m/s"],
      "speech": "Ippudu 400 meters ni 20 seconds tho divide chesthe speed 20 meters per second."
    },
    {
      "label": "Step 3: Convert to kilometres per hour",
      "lines": ["20 x 18/5 = 72 km/h"],
      "speech": "20 meters per second ni 18 by 5 tho multiply chesthe 72 kilometres per hour."
    }
  ],
  "answer": {
    "display": "72 km/h",
    "speech": "So the answer is 72 kilometres per hour, option A.",
    "correct_option": "A"
  }
}
```
