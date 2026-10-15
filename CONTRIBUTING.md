# Contributing

## Development checks

```bash
python -m pip install ".[dev]"
pytest -q
```

Keep question content, labels, colors, fonts, and timing in input JSON or theme data. Add tests for new scene behavior, plugin fallback, theme parsing, or output constraints. Do not commit `.env`, generated videos, or cache files.

## Add a scene

1. Add a renderer module under `src/solution_video/scenes/` implementing the existing scene protocol.
2. Register it in the scene builder/catalog and connect it to content-driven schema data.
3. Keep the renderer independent of providers, CLI arguments, and bot details.
4. Add a focused test and confirm phone-safe margins and readable type.

## Add a visual plugin

1. Add a focused module under `src/solution_video/plugins/`.
2. Define a typed, validated data contract; do not let plugin code change the answer or verification result.
3. Register the plugin and retain the generic-scene fallback for unknown or invalid plugin input.
4. Test the valid rendering path and the fallback path.

## Add a theme

1. Add a JSON theme under `themes/` using the shape of `themes/default.json`.
2. Reference fonts that ship with the package and retain a contrast/readability suitable for a phone screen.
3. Validate it with `solution-video render --theme themes/<name>.json ... --no-voice`.

## Pull requests

Keep changes scoped, add/update documentation when behavior changes, run the tests, and include generated media only as CI artifacts—not in Git.
