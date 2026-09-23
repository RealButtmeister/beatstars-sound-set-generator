"""Evidence-selected sound-set MIDI export; no network calls or dependencies."""
from __future__ import annotations
import argparse
import csv
import html
import json
import re
import unicodedata
import tempfile
from datetime import date, datetime
from pathlib import Path
from midi_export import write_soundset

BASE = Path(__file__).resolve().parent
SCOPES = {'all_time', 'recent_releases'}

def normal(text):
    text = str(text).lower().replace('r&b', 'rnb').replace('r & b', 'rnb')
    text = ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()

def phrase(text, term):
    return (' ' + normal(term) + ' ') in (' ' + normal(text) + ' ')

def load_rows(path):
    rows, seen = [], set()
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        required = {'scope', 'rank', 'track_id', 'title', 'producer', 'bpm', 'tags'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('The CSV needs: ' + ', '.join(sorted(required)))
        for line, raw in enumerate(reader, 2):
            if not any(raw.values()):
                continue
            if raw.get('ad', '').strip().lower() in {'1', 'true', 'yes', 'ad'}:
                continue
            if raw.get('rank', '').strip() == '-':
                continue
            scope = raw['scope'].strip()
            ident = raw['track_id'].strip()
            if scope not in SCOPES or not ident.isdigit():
                raise ValueError(f'CSV row {line}: invalid scope or numeric track ID')
            if not raw['title'].strip() or not raw['producer'].strip():
                raise ValueError(f'CSV row {line}: title and producer are required')
            rank = int(raw['rank']) if raw['rank'].strip() else None
            bpm = float(raw['bpm']) if raw['bpm'].strip() else None
            if rank is not None and rank < 1:
                raise ValueError(f'CSV row {line}: rank must be positive')
            if bpm is not None and not 20 <= bpm <= 400:
                raise ValueError(f'CSV row {line}: BPM must be between 20 and 400')
            if (scope, ident) in seen:
                continue
            seen.add((scope, ident))
            rows.append(dict(scope=scope, rank=rank, track_id=ident,
                title=raw['title'].strip(), producer=raw['producer'].strip(), bpm=bpm,
                tags=[s.strip() for s in raw['tags'].split('|') if s.strip()],
                url='https://www.beatstars.com/TK' + ident))
    if not rows:
        raise ValueError('No non-ad chart observations were found in the CSV')
    return rows

def match_profiles(row, palettes):
    text = row['title'] + ' ' + ' '.join(row['tags'])
    ids = {p['id'] for p in palettes if any(phrase(text, a) for a in p['aliases'])}
    # Seller cross-tags are ambiguous. Specific evidence wins over generic tags.
    if phrase(text, 'melodic') and phrase(text, 'trap'):
        ids.add('melodic_trap')
    if phrase(text, 'hardtraptypebeat') or phrase(text, '21 savage'):
        ids.add('trap')
    if phrase(text, 'drake') and phrase(text, 'rnb'):
        ids.add('dark_rnb')
    if phrase(text, 'trap rnb'):
        ids.add('dark_rnb')
    if 'pop_rock' in ids and not any(phrase(text, term) for term in
            ['frank ocean', 'mac miller', 'bedroom pop', 'alt pop', 'alternative pop']):
        ids.discard('alt_pop')
    if 'dark_rnb' in ids and not any(phrase(text, x) for x in
            ['rnb', 'partynextdoor', 'brent faiyaz', '6lack', 'lithe', '4batz', 'tory lanez']):
        ids.discard('dark_rnb')
    if any(phrase(row['title'], x) for x in ['not trap', 'no trap']):
        ids.discard('trap')
        ids.discard('melodic_trap')
    specific_trap = {'atmospheric_trap', 'melodic_trap', 'southern_trap',
                     'detroit_flint', 'rage', 'emo_rap', 'drill', 'trap_metal'}
    if ids & specific_trap:
        ids.discard('trap')
    if ids & {'y2k_pop', 'alt_pop', 'pop_punk', 'pop_rock', 'indie_rock', 'krushclub'}:
        ids.discard('pop')
    if ids & {'dark_rnb', 'y2k_pop', 'reggaeton', 'afrobeats'}:
        ids.discard('contemporary_rnb')
    return ids & {p['id'] for p in palettes}

def select_sets(rows, palettes, scope='all'):
    evidence = {p['id']: [] for p in palettes}
    unmatched = []
    for row in rows:
        if scope != 'all' and row['scope'] != scope:
            continue
        matched = match_profiles(row, palettes)
        if not matched:
            unmatched.append(row)
        for ident in matched:
            evidence[ident].append(row)
    active = [dict(p, evidence=evidence[p['id']]) for p in palettes if evidence[p['id']]]
    active.sort(key=lambda p: (-len({r['track_id'] for r in p['evidence']}), p['name']))
    return active, unmatched

def load_palettes(path=BASE / 'palettes.json'):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    palettes = data if isinstance(data, list) else data['profiles']
    seen = set()
    for p in palettes:
        if not re.fullmatch(r'[a-z0-9_]+', p['id']) or p['id'] in seen:
            raise ValueError('Palette IDs must be unique safe names')
        seen.add(p['id'])
        if not isinstance(p['aliases'], list) or not p['aliases']:
            raise ValueError('Each palette needs aliases')
    return palettes

def validate_date(value):
    return date.fromisoformat(value).isoformat()

def export_collection(destination, rows, palettes, observed_at, scope='all', chosen=None):
    observed_at = validate_date(observed_at)
    active, unmatched = select_sets(rows, palettes, scope)
    if chosen is not None:
        active = [p for p in active if p['id'] in chosen]
    if not active:
        raise ValueError('No matched sound sets in this selection. Review the CSV tags.')
    parent = Path(destination)
    parent.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='BeatStars Sets ' + observed_at + ' - ', dir=parent))
    cards = []
    for index, p in enumerate(active, 1):
        stem = f'{index:02d} {p["name"]}'
        stem = re.sub(r'[<>:"/\\|?*]', '-', stem).rstrip(' .')
        kit = folder / stem
        roles = write_soundset(kit / 'Sound Set.mid', p['name'], p['lanes'])
        (kit / 'Roles.json').write_text(json.dumps(roles, indent=2), encoding='utf-8')
        info = dict(p, observed_at=observed_at, evidence_type='chart_presence',
                    sound_source='Suggested palette inferred from titles/tags; reference audio not analyzed',
                    tempo_in_midi=False, actual_audio_included=False)
        (kit / 'Sound Set.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
        lines = [p['name'], '=' * len(p['name']), '', p['description'], '',
                 'Suggested starting tempo: ' + str(p['bpm_hint']),
                 'Set tempo yourself in FL Studio. Source BPMs may use half/double-time counting.', '',
                 'SOUND CHOICES (suggestions, not identifications from the reference audio)']
        lines += [l['name'] for l in p['lanes']]
        lines += ['', 'REFERENCES - observed ' + observed_at]
        for r in p['evidence']:
            ranking = f" #{r['rank']}" if r['rank'] else ' (rank not captured)'
            lines += [r['scope'] + ranking + ': ' + r['title'], r['url']]
        lines += ['', 'IMPORT', 'Drag Sound Set.mid into FL Studio and import as separate tracks.',
                  'Assign your samples or instruments using the lane names. GM sounds are rough placeholders.',
                  'Each lane has one 30-tick placeholder note. Delete it before composing.',
                  'Roles.json maps these lanes for Genre MIDI Studio; it does not add a new composition engine.',
                  'No audio samples, synth presets, full beat, sales totals or automatic live refresh are included.']
        (kit / 'READ ME.txt').write_text('\n'.join(lines), encoding='utf-8')
        url = html.escape(stem + '/Sound Set.mid', quote=True)
        ref_list = ''.join('<li><a href="' + html.escape(r['url'], quote=True) + '">' +
                           html.escape(r['title']) + '</a> <small>' + html.escape(r['scope']) + '</small></li>'
                           for r in p['evidence'])
        sounds = ''.join('<li>' + html.escape(l['name']) + '</li>' for l in p['lanes'])
        cards.append(f'<article><h2>{html.escape(p["name"])}</h2><p>{html.escape(p["description"])}</p>'
                     f'<p class="meta">{len(p["lanes"])} lanes · Suggested tempo {html.escape(str(p["bpm_hint"]))}</p>'
                     f'<a class="download" href="{url}" download>Save MIDI sound set</a>'
                     f'<details><summary>Sound choices</summary><ul>{sounds}</ul></details>'
                     f'<details><summary>{len(p["evidence"])} chart references</summary><ul>{ref_list}</ul></details></article>')
    coverage_rows = [r for r in rows if scope == 'all' or r['scope'] == scope]
    report = dict(observed_at=observed_at, scope=scope, observations=len(coverage_rows),
        unique_tracks=len({r['track_id'] for r in coverage_rows}), sets=len(active),
        profiles=[p['id'] for p in active], unmatched=unmatched,
        limitations=['Snapshot sample, not an exhaustive market census',
                     'Recent releases is a release-date filter, not a sales-performance period',
                     'No verified sales counts; chart presence is a popularity proxy',
                     'Original suggested sound palettes; reference audio not analyzed',
                     'Import updated observations.csv to refresh; no automatic chart feed'])
    (folder / 'Coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    with (folder / 'References.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['scope','rank','track_id','title','producer','bpm','tags','url'])
        writer.writeheader()
        for r in coverage_rows:
            writer.writerow(dict(r, tags='|'.join(r['tags'])))
    notes = ('Observed ' + observed_at + f' · {len(coverage_rows)} chart observations · {len(active)} sound families. '
             'A dated sample, not the whole market. Ads excluded. Chart presence does not verify sales. '
             '“Recent releases” filters release dates. Sounds below are production suggestions inferred from titles/tags; audio was not analyzed.')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>BeatStars Sound Sets</title><style>
body{font:16px/1.5 system-ui,sans-serif;background:#11131a;color:#eceff5;margin:0}main{max-width:1100px;margin:auto;padding:48px 24px}h1{font-size:38px;line-height:1.1;margin:12px 0}h2{font-size:21px}a{color:#92dbce}small,.meta{color:#afbacb}header p{max-width:850px;color:#bac5d6}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px;margin:30px 0}article{background:#1c202c;border:1px solid #363d4e;border-radius:16px;padding:22px}.download{display:inline-block;background:#8cd9c6;color:#101714;border-radius:8px;padding:9px 13px;font-weight:650;text-decoration:none;margin:8px 0 15px}details{margin-top:10px}summary{cursor:pointer}li{margin:6px 0}input{box-sizing:border-box;width:100%;padding:14px;background:#1c202c;color:#fff;border:1px solid #586276;border-radius:8px;font:inherit}.eyebrow{color:#8cd9c6;letter-spacing:2px;font-size:12px}footer{color:#b6c1d2}
</style><main><header><span class="eyebrow">MIDI PALETTES / FL STUDIO</span><h1>Sounds with a reference.</h1><p>'''
    page += html.escape(notes) + '</p><p>Import a MIDI as separate tracks, choose sounds by the lane names, then clear the tiny placeholder notes. Set your own DAW tempo.</p></header>'
    page += '<label for="search">Find a style or sound</label><input id="search" placeholder="Try rage, guitar, R&amp;B...">'
    page += '<div class="grid">' + ''.join(cards) + '</div>'
    page += '<footer><p>' + str(len(unmatched)) + ' observations could not be classified confidently; see Coverage.json. The generator includes every matched family in the selected snapshot.</p><p>No actual audio or synth presets are included. To update the collection, import a new observations CSV in the generator.</p></footer>'
    page += "<script>document.querySelector('#search').addEventListener('input',e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('article').forEach(a=>a.hidden=!a.textContent.toLowerCase().includes(q));});</script></main></html>"
    (folder / 'START HERE.html').write_text(page, encoding='utf-8')
    return folder, report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, required=True, help='Your observations CSV; no chart snapshot is bundled')
    parser.add_argument('--output', type=Path, default=BASE/'Generated Sets')
    parser.add_argument('--date', required=True, help='Date the chart was observed, YYYY-MM-DD')
    parser.add_argument('--scope', choices=['all', 'all_time', 'recent_releases'], default='all')
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()
    rows, palettes = load_rows(args.csv), load_palettes()
    if args.list:
        active, unmatched = select_sets(rows, palettes, args.scope)
        for p in active:
            print(p['name'] + ': ' + str(len(p['evidence'])) + ' references')
        print(str(len(unmatched)) + ' observations need review')
        return
    folder, report = export_collection(args.output, rows, palettes, args.date, args.scope)
    print(f'Created {report["sets"]} sound sets: {folder}')

if __name__ == '__main__':
    main()
