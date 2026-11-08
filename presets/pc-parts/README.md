# PC & laptop parts: 3D explainer preset

A ready-made batch of 10 videos, one per part (CPU, GPU, RAM, SSD/HDD, motherboard,
PSU, cooling, laptop internals, laptop battery, screens). Each video takes the part
apart in 3D.

| File | What it does |
| --- | --- |
| `system_prompt.txt` | Script style: hook → where it sits → exploded breakdown → everyday analogy → which specs matter |
| `tasks.jsonl` | One line per video: the topic plus 4 scene prompts written for an AI video source ("exploded view, photorealistic 3D render…") |

## Run it

Use the same AI video source you use for your car videos (`volcengine_seedance`,
`jalapeno`, `wavespeed`, `muapi`, `ofox`, `infistar`, `metaso_minimax`). Those sources
send each `video_terms` entry as a generation prompt, which is where the 3D look
comes from. Stock sources like Pexels search for footage with these terms instead,
so you'll get real hardware clips rather than 3D renders.

Generate only the scripts first. This is free apart from LLM calls, and lets you
check the wording:

```sh
uv run python cli.py --batch-file presets/pc-parts/tasks.jsonl \
  --custom-system-prompt "$(cat presets/pc-parts/system_prompt.txt)" \
  --paragraph-number 5 --stop-at script
```

Full render (Seedance shown here, so swap in your source and its `--confirm-*-charge` flag):

```sh
uv run python cli.py --batch-file presets/pc-parts/tasks.jsonl \
  --custom-system-prompt "$(cat presets/pc-parts/system_prompt.txt)" \
  --paragraph-number 5 \
  --video-source volcengine_seedance --confirm-seedance-charge \
  --video-concat-mode sequential --video-aspect 9:16
```

`--video-concat-mode sequential` plays the scenes in the order they're written
(install → exploded view → how it works → detail), so they line up with the
script. The paid sources charge **per clip**: 10 videos × 4 scenes = 40 clips.
To test one video, cut `tasks.jsonl` down to one line first.

## In the WebUI

Paste `system_prompt.txt` into the custom system prompt box, set paragraphs to 5,
enter a topic from `tasks.jsonl`, and paste that line's scene prompts into the
keywords box, separated by commas. Note that the WebUI splits on commas, so
each style phrase becomes its own clip. To keep a prompt together, shorten it to
something like `CPU exploded view 3D render`.

## Adding more parts

Add a line to `tasks.jsonl`:

```json
{"video_subject": "What a NIC / Wi-Fi card does", "video_terms": ["Wi-Fi card exploded view with antennas, photorealistic 3D render, studio lighting, dark background, slow orbit camera"]}
```

To change the visual style for every clip (e.g. a blueprint or neon look), edit the
style suffix on each prompt. Any per-task field from `VideoParams` (voice,
aspect, subtitles) can also go on a line to override the CLI defaults.
