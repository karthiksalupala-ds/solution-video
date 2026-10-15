# Solution to steps

Return one JSON object only. Use only the supplied input. Do not invent facts, sources, companies, values, or formulas.

Create 2 to 5 steps. Each has `label`, `lines` (one to four short display equations/text lines, max 90 characters each), and `speech` (natural Tanglish in Latin script; do not read raw mathematical symbols). `emphasis` and `visual` are optional. Include `answer` as an object with `display` exactly equal to the supplied final answer and `correct_option` exactly equal to the supplied option letter. If present, `tip` must be an object with a `display` field and optional `speech` field; never return a bare string.

Never include a `source` field. Do not alter the question, options, or final answer.
