# BeatStars Sound Set Generator

Turn your own dated chart observations into suggested sound palettes and named MIDI instrument lanes. The generator matches titles and tags against original production palettes; it does not listen to reference audio, scrape a live chart, or verify sales.

## Run

Use Python 3.10 or newer with Tkinter. There are no third-party runtime packages.

```text
python soundset_app.py
```

On Windows you can use `Start.cmd`. It prefers `.venv\Scripts\python.exe` and otherwise uses `python` on PATH. The window opens without chart data; choose an observations CSV to begin.

## Supply observations

Copy `observations.example.csv` to a local file and fill it with your own observations. The provided file contains headers only; no reference tracks, producers, downloaded music, or old chart snapshot is bundled.

| Column | Meaning |
| --- | --- |
| `scope` | `all_time` or `recent_releases` |
| `rank` | Positive integer, or empty when not captured; `-` excludes the row |
| `track_id` | Numeric BeatStars track identifier, used to construct its reference link |
| `title` | Observed track title |
| `producer` | Observed producer name |
| `bpm` | Optional numeric tempo between 20 and 400 |
| `tags` | Descriptive tags separated by `|` |
| `ad` | Optional; `true`, `yes`, `1`, or `ad` excludes an advertisement |

Choose the collection date and chart view, review the matching families, then generate all matched families or only the selected ones. Search filters the visible list; “Generate all matched” includes every matched family in the chosen chart view. An observations file must contain at least one non-ad row.

## Use the export

Each sound set contains named MIDI lanes, a `Roles.json` role map for Genre MIDI Studio, palette notes, and links to the observations you supplied. The generated HTML index helps browse the collection. Sound suggestions and General MIDI program hints are starting points, not exact artist presets.

Import `Sound Set.mid` into FL Studio as separate tracks, assign your own instruments and samples, and remove the tiny placeholder notes before composing. No audio, synth presets, or full beat is produced.

## Command line

```text
python generator.py --csv observations.csv --date 2026-01-01 --list
python generator.py --csv observations.csv --date 2026-01-01 --output exports
```

Use the actual observation date. Exports receive a new folder; existing collections are not overwritten. Processing stays local. Opening the exported HTML or its links uses your browser. This is an independent tool, not an official BeatStars application.

## License

No application license has been selected for this source release. Public visibility alone does not grant a license to reuse, modify, or redistribute it. Existing third-party notices, where supplied, are retained and apply to their respective components.
