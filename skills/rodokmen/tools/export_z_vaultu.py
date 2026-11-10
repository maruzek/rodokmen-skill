#!/usr/bin/env python3
"""Export z Obsidian vaultu do datových souborů webu (fáze 5).

Vault je zdroj pravdy. Z poznámek v `rodokmen/` se sestaví soubory, které čte `tools/export_web.py` v projektu webu
(`data/osoby.py`, `zaznamy.json`, `svazky.json`, `prepisy.json`, `zvyrazneni.json`, `strom.py`, `import/gedcom.json`,
výřezy do `vyrezy/`). Zveřejní se JEN to, co má ve frontmatteru povolení:
  verejne: true       plné údaje (jen zemřelé osoby, zápisy)
  verejne: omezene    jen jméno a rok narození (žijící i zemřelí); výchozí web tak ukáže vějíř od žijící výchozí osoby
  (cokoli jiné)       nejde ven
Před exportem musí `kontrola_soukromi.py` skončit bez chyb; po exportu se kontroluje, že se v souborech neobjevilo
jméno neveřejné žijící osoby. Nic nepřepisuje, dokud není zadáno `--zapsat`.

Použití (`--vault` = kořen vaultu, `--slozka` = podsložka s rodokmenem, výchozí `rodokmen`; formát poznámek viz
`reference/obsidian.md`; `--projekt` = projekt webu, výchozí aktuální složka, má-li `data/`):
  python3 -I SKILL_DIR/tools/export_z_vaultu.py --vault <vault> --navrh      # co by se mělo zveřejnit (jen výpis)
  python3 -I SKILL_DIR/tools/export_z_vaultu.py --vault <vault> --oznacit    # nastaví navržená `verejne` (po souhlasu uživatele)
  python3 -I SKILL_DIR/tools/export_z_vaultu.py --vault <vault> --projekt <web>   # export do <web>/pracovni/export_z_vaultu/
  python3 -I SKILL_DIR/tools/export_z_vaultu.py --vault <vault> --projekt <web> --zapsat   # a přepíše <web>/data a <web>/vyrezy
Kontrolu soukromí bere z `<vault>/_nastroje/kontrola_soukromi.py`, jinak z `kontrola_vaultu.py` vedle tohoto skriptu.
"""
import argparse, datetime, json, os, pathlib, re, shutil, subprocess, sys
import yaml
import hashlib
TOOLS = pathlib.Path(__file__).resolve().parent
VAULT = R = None   # nastaví main() podle --vault / --slozka


def crid(klic):
    """Deterministické cr_id ve tvaru pluginu Charted Roots (aaa-000-aaa-000) z čitelného klíče."""
    b = hashlib.sha256(klic.encode('utf-8')).digest()
    L = lambda x: chr(97 + x % 26)
    return f'{L(b[0])}{L(b[1])}{L(b[2])}-{int.from_bytes(b[3:5], "big") % 1000:03d}-{L(b[5])}{L(b[6])}{L(b[7])}-{int.from_bytes(b[8:10], "big") % 1000:03d}'

LIMIT = 110
NOW = datetime.date.today().year
MON = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
ST = {'doloženo': 'doc', 'pravděpodobné': 'prob', 'rodina': 'fam', 'cizí-strom': 'mh', 'hypotéza': 'unk', 'neznámé': 'unk'}
SKIP_SECTIONS = ('Původ', 'Citace z exportu', 'Zdroj', 'Příbuzenství', 'Co o osobě víme')


def split(p):
    t = p.read_text(encoding='utf-8')
    m = re.match(r'---\n(.*?)\n---\n?(.*)', t, re.S)
    return (yaml.safe_load(m.group(1)) or {}, m.group(2)) if m else ({}, t)


def year(v):
    m = re.search(r'\d{4}', str(v or ''))
    return int(m.group()) if m else None


def gdate(v):
    """ISO / ABT / rok → formát GEDCOM ('13 SEP 1918', 'ABT 1683')."""
    s = str(v or '').strip().strip('"')
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m: return f'{int(m[3])} {MON[int(m[2]) - 1]} {m[1]}'
    m = re.fullmatch(r'(\d{4})-(\d{2})', s)
    if m: return f'{MON[int(m[2]) - 1]} {m[1]}'
    return s


def load():
    notes = {}
    for p in R.rglob('*.md'):
        if '_plugin' in p.parts: continue
        fm, body = split(p)
        notes[p.stem] = dict(path=p, fm=fm, body=body)
    return notes


def person_state(fm):
    """deceased / living / unknown podle stejných pravidel jako kontrola_soukromi.py."""
    died, s, b = fm.get('died'), fm.get('soukromi'), year(fm.get('born'))
    if s == 'zijici': return 'living'
    if died or s == 'zemrely': return 'deceased'
    if b is not None: return 'deceased' if NOW - b >= LIMIT else 'living'
    return 'unknown'


def proposal(notes):
    """Návrh `verejne`: zemřelí → true; žijící přímí předci (s kekule) → omezene; zápisy odkazované veřejnými osobami → true."""
    out = {}
    for slug, n in notes.items():
        fm = n['fm']
        if fm.get('cr_type') == 'person' and fm.get('verejne') in (False, None):
            st = person_state(fm)
            if st == 'deceased': out[slug] = True
            elif st == 'living' and fm.get('kekule') is not None: out[slug] = 'omezene'
    pub = {s for s, v in out.items() if v is True}
    for slug, n in notes.items():
        fm = n['fm']
        if fm.get('cr_type') == 'source' and fm.get('klic') and fm.get('verejne') in (False, None):
            linked = [re.match(r'\[\[([^\]|]+)', x).group(1) for x in (fm.get('osoby') or []) if isinstance(x, str) and x.startswith('[[')]
            if any(l in pub or notes.get(l, {}).get('fm', {}).get('verejne') is True for l in linked): out[slug] = True
    return out


def apply_flags(notes, flags):
    for slug, v in flags.items():
        p = notes[slug]['path']
        t = p.read_text(encoding='utf-8')
        val = 'true' if v is True else str(v)
        if re.search(r'^verejne:.*$', t, re.M): t = re.sub(r'^verejne:.*$', f'verejne: {val}', t, count=1, flags=re.M)
        else: t = re.sub(r'\n---\n', f'\nverejne: {val}\n---\n', t, count=1)
        p.write_text(t, encoding='utf-8')


# ---------- text ----------
def clean(text, notes, pubset, limited=False):
    """Markdown → prostý text; odkazy na neveřejné poznámky nahradí obecným textem."""
    def link(m):
        tgt = m.group(1).strip()
        label = m.group(2) or (notes.get(tgt, {}).get('fm', {}).get('name') or tgt)
        return label if tgt in pubset else 'jiná osoba (nezveřejněno)'
    t = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    t = re.sub(r'!\[\[[^\]]*\]\]', '', t)
    t = re.sub(r'\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]', link, t)
    t = re.sub(r'\*\*|__|`', '', t)
    return t


def sections(body):
    parts = re.split(r'^## (.+)$', body, flags=re.M)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def bullets(s): return [re.sub(r'^[-*]\s+', '', l).strip() for l in s.splitlines() if re.match(r'^\s*[-*]\s', l)]


def yearlabel(fm, limited):
    b, d = gdate(fm.get('born')), gdate(fm.get('died'))
    yb, yd = year(b), year(d)
    q = lambda v: 'asi ' if str(v).startswith(('ABT', 'CAL', 'EST')) else ''
    if limited: return f'* {q(b)}{yb}' if yb else ''
    if yb and yd: return f'{q(b)}{yb}–{q(d)}{yd}'
    if yb: return f'* {q(b)}{yb}'
    if yd: return f'† {q(d)}{yd}'
    return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--vault', required=True, help='kořen vaultu')
    ap.add_argument('--slozka', default='rodokmen', help='podsložka vaultu s rodokmenem')
    ap.add_argument('--projekt', default=os.getcwd(), help='projekt webu (má data/)')
    ap.add_argument('--ven')
    ap.add_argument('--navrh', action='store_true')
    ap.add_argument('--oznacit', action='store_true')
    ap.add_argument('--zapsat', action='store_true')
    a = ap.parse_args()
    global VAULT, R
    VAULT = pathlib.Path(a.vault).expanduser().resolve(); R = VAULT / a.slozka
    if not R.is_dir(): sys.exit(f'Složka {R} neexistuje.')
    notes = load()
    if a.navrh or a.oznacit:
        pr = proposal(notes)
        for v, title in ((True, 'verejne: true'), ('omezene', 'verejne: omezene (jen jméno a rok narození)')):
            names = sorted(f"{notes[s]['fm'].get('name', s)} [{s}]" for s, x in pr.items() if x == v)
            print(f'\n== {title}: {len(names)}'); print('\n'.join('  ' + n for n in names))
        unk = [s for s, n in notes.items() if n['fm'].get('cr_type') == 'person' and person_state(n['fm']) == 'unknown']
        print(f'\n== bez dat (nenavrženo, vyžaduje rozhodnutí): {len(unk)}')
        if a.oznacit: apply_flags(notes, pr); print('\nZnačky `verejne` nastaveny.')
        return
    # brána: kontrola soukromí
    kontrola = VAULT / '_nastroje' / 'kontrola_soukromi.py'
    if not kontrola.exists(): kontrola = TOOLS / 'kontrola_vaultu.py'
    rc = subprocess.run([sys.executable, '-I', str(kontrola), str(VAULT), a.slozka])
    if rc.returncode: sys.exit('STOP: kontrola_soukromi.py hlásí chyby, export se nespustil.')
    proj = pathlib.Path(a.projekt).expanduser().resolve()
    if not a.zapsat and not (proj / 'data').is_dir(): print(f'Poznámka: {proj} nemá data/, vzorek osoby.py/LINES se neopíše.')
    out = pathlib.Path(a.ven) if a.ven else proj / 'pracovni' / 'export_z_vaultu'
    if out.exists(): shutil.rmtree(out)
    (out / 'data' / 'import').mkdir(parents=True); (out / 'vyrezy').mkdir()

    persons = {s: n for s, n in notes.items() if n['fm'].get('cr_type') == 'person'}
    full = {s for s, n in persons.items() if n['fm'].get('verejne') is True and person_state(n['fm']) != 'living'}
    lim = {s for s, n in persons.items() if n['fm'].get('verejne') == 'omezene'}
    exp = full | lim
    if not exp: sys.exit('Žádná osoba nemá verejne: true/omezene. Spusť --navrh a po souhlasu uživatele --oznacit.')
    pid = lambda s: persons[s]['fm'].get('gedcom_id') or f"@V-{persons[s]['fm']['cr_id']}@"
    link_slug = lambda v: (re.match(r'\[\[([^\]|#]+)', v).group(1).strip() if isinstance(v, str) and v.startswith('[[') else None)
    rel = lambda fm, k: [x for x in ([fm.get(k)] if isinstance(fm.get(k), str) else (fm.get(k) or [])) if link_slug(x)]
    recs = {s: n for s, n in notes.items() if n['fm'].get('cr_type') == 'source' and n['fm'].get('klic') and n['fm'].get('verejne') is True}
    pubset = exp | set(recs)

    # --- gedcom snapshot ---
    gp, events, fams = {}, [], {}
    for s in sorted(exp):
        fm = persons[s]['fm']; i = pid(s)
        gp[i] = dict(name=fm['name'].split(' (')[0] if s in lim or True else fm['name'], origin='mh' if fm.get('jistota') == 'cizí-strom' else 'fam',
                     citations=[], verified=False, notes=[], privacy_limited=(s in lim))
        if fm.get('born'): events.append(dict(id=f'{i}:b', owner=i, type='BIRT', date=gdate(fm['born']), place=fm.get('birth_place', '') if s in full else '', has_date_or_place=True))
        if s in full: events.append(dict(id=f'{i}:d', owner=i, type='DEAT', date=gdate(fm.get('died')), place=fm.get('death_place', '') or '', has_date_or_place=bool(fm.get('died'))))
    pairs = {}
    for s in exp:
        fm = persons[s]['fm']
        f = link_slug(fm.get('father')); m = link_slug(fm.get('mother'))
        f = f if f in exp else None; m = m if m in exp else None
        if f or m: pairs.setdefault((f, m), set()).add(s)
        sp = link_slug(fm.get('spouse'))
        if sp in exp and s < sp: pairs.setdefault((s, sp) if fm.get('sex') != 'F' else (sp, s), set())
        for c in rel(fm, 'children'):
            cs = link_slug(c)
            if cs in exp:
                cf, cm = link_slug(persons[cs]['fm'].get('father')), link_slug(persons[cs]['fm'].get('mother'))
                if s in (cf, cm): pairs.setdefault((cf if cf in exp else None, cm if cm in exp else None), set()).add(cs)
    for (f, m), kids in sorted(pairs.items(), key=lambda x: str(x[0])):
        fid = f"@F-{crid('rodina_' + str(f) + '_' + str(m))}@"
        sub = [dict(tag=t, val=pid(x), _sub=[]) for t, x in (('HUSB', f), ('WIFE', m)) if x] + [dict(tag='CHIL', val=pid(k), _sub=[]) for k in sorted(kids)]
        fams[fid] = dict(_id=fid, _type='FAM', _sub=sub)
    root_slug = next((s for s in exp if persons[s]['fm'].get('kekule') == 1), None)
    if not root_slug: sys.exit('Výchozí osoba (kekule: 1) není označena jako veřejná/omezená.')
    snap = dict(schema_version=1, source_file='vault', source_export_date=str(datetime.date.today()), sha256='', root=pid(root_slug),
                root_provisional=True, imported_on=str(datetime.date.today()),
                counts=dict(persons=len(gp), families=len(fams)), persons=gp, events=events, records=fams)
    (out / 'data' / 'import' / 'gedcom.json').write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding='utf-8')

    # --- osoby.py ---
    rec_of = lambda fm: [notes[link_slug(x)]['fm']['klic'] for x in (fm.get('zapisy') or []) if link_slug(x) in recs]
    P, SIDE = {}, []
    adj = {}
    for s in exp:
        fm = persons[s]['fm']
        for k in ('father', 'mother', 'spouse'):
            t = link_slug(fm.get(k))
            if t in exp: adj.setdefault(s, set()).add(t); adj.setdefault(t, set()).add(s)
        for c in rel(fm, 'children'):
            t = link_slug(c)
            if t in exp: adj.setdefault(s, set()).add(t); adj.setdefault(t, set()).add(s)
    kek = {s: persons[s]['fm']['kekule'] for s in exp if persons[s]['fm'].get('kekule') is not None}
    for s in sorted(exp, key=lambda x: (kek.get(x, 10**9), x)):
        n = persons[s]; fm = n['fm']; sec = sections(n['body']); limited = s in lim
        if limited: facts, note = [], 'Údaje jen základní.'
        else:
            facts = [clean(b, notes, pubset) for b in bullets(sec.get('Co o osobě víme', ''))]
            note = ' '.join(clean(v, notes, pubset).replace('\n', ' ') for k, v in sec.items() if not k.startswith(SKIP_SECTIONS))
        entry = dict(n=fm['name'], y=yearlabel(fm, limited), st=ST.get(fm.get('jistota'), 'unk'), f=facts, r=[] if limited else rec_of(fm), note=note, gedcom_id=pid(s))
        if s in kek: P[kek[s]] = entry
        else:
            near = next((kek[t] for t in sorted(adj.get(s, ())) if t in kek), None)
            if near is not None: SIDE.append(dict(k=near, n=fm['name'], t=note, r=entry['r'], st=entry['st'], gedcom_id=pid(s)))
    lines = {}
    old = {}
    try: exec((proj / 'data' / 'osoby.py').read_text(encoding='utf-8-sig'), old)
    except Exception: pass
    LINES, ISSUES = old.get('LINES', {}), old.get('ISSUES', [])
    py = '# Vygenerováno z vaultu skriptem export_z_vaultu.py. Neupravovat ručně, měň poznámky ve vaultu.\n'
    py += 'P = ' + repr(P) + '\nLINES = ' + repr(LINES) + '\nSIDE = ' + repr(SIDE) + '\nISSUES = ' + repr(ISSUES) + '\nHYPOTEZY = []\nSAME = {}\n'
    (out / 'data' / 'osoby.py').write_text(py, encoding='utf-8')
    warn = {pid(s): [x for x in (persons[s]['fm'].get('varovani') or [])] for s in full if persons[s]['fm'].get('varovani')}
    (out / 'data' / 'strom.py').write_text('ADDED_PERSONS = {}\nFAMILY_FATHERS = {}\nADDED_FAMILIES = []\nPERSON_WARNINGS = ' + repr(warn) + '\nRELATION_WARNINGS = []\n', encoding='utf-8')

    # --- zápisy ---
    zaz, svz, prep = [], {}, {}
    old_hl = {}
    hp = proj / 'data' / 'zvyrazneni.json'
    if hp.exists(): old_hl = json.loads(hp.read_text(encoding='utf-8-sig'))
    hl = {}
    for s, n in sorted(recs.items()):
        fm = n['fm']; sec = sections(n['body']); klic = fm['klic']
        par = link_slug(fm.get('source_parent'))
        if par and par in notes:
            pf = notes[par]['fm']; key = par.replace('svazek-', '', 1).replace('-', '_')
            desc = re.search(r'\*\*Popis:\*\*\s*(.+)', notes[par]['body'])
            svz.setdefault(key, dict(archiv=pf.get('repository', ''), portal=pf.get('portal', 'archivu'), svazek=pf.get('title', key), popis=desc[1].strip() if desc else '', url=pf.get('source_repository_url', '')))
        else: key = ''
        dm = re.search(r'\*\*Datum zápisu:\*\*\s*([^·\n]+)', n['body'])
        zaz.append(dict(klic=klic, svazek=key, snimek=fm.get('snimek', ''), druh=fm.get('druh', 'J'), datum=(dm[1].strip() if dm else ''), nazev=fm.get('title', klic),
                        shrnuti=clean(sec.get('Co zápis dokládá', ''), notes, pubset).replace('\n', ' '), odkaz=fm.get('source_repository_url', '')))
        prep[klic] = dict(orig=sec.get('Přepis originálu', ''), cs=clean(sec.get('Český překlad / vysvětlení', ''), notes, pubset))
        if klic in old_hl: hl[klic] = old_hl[klic]
        img = n['path'].with_suffix('.jpg')
        if img.exists(): shutil.copy(img, out / 'vyrezy' / f'{klic}.jpg')
    for name, obj in (('zaznamy.json', zaz), ('svazky.json', svz), ('prepisy.json', prep), ('zvyrazneni.json', hl)):
        (out / 'data' / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding='utf-8')

    # --- brána po exportu: jména neveřejných žijících osob nesmí být ve výstupu ---
    blob = ''.join(p.read_text(encoding='utf-8', errors='ignore') for p in (out / 'data').rglob('*') if p.is_file())
    nm_of = lambda n: str(n['fm'].get('name', '')).split(' (')[0]
    safe = {nm_of(n) for s, n in persons.items() if s in exp or person_state(n['fm']) != 'living'}   # kolize jmen s veřejnými/zemřelými nejdou rozlišit
    leaks = sorted({nm_of(n) for s, n in persons.items() if s not in exp and person_state(n['fm']) == 'living'
                    and len(nm_of(n)) > 5 and nm_of(n) not in safe and nm_of(n) in blob})
    clash = sorted({nm_of(n) for s, n in persons.items() if s not in exp and person_state(n['fm']) == 'living' and nm_of(n) in safe and nm_of(n) in blob})
    if clash: print(f'POZOR: jména neveřejných žijících osob shodná s veřejnými osobami (ověř ručně, zda text patří předkovi): {clash}')
    if leaks: sys.exit(f'STOP: ve výstupu je jméno neveřejné žijící osoby: {leaks} (výstup nechán v {out})')
    print(f'Export OK: {len(P)} předků, {len(SIDE)} příbuzných, {len(gp)} osob celkem, {len(fams)} rodin, {len(zaz)} zápisů -> {out}')
    if a.zapsat:
        for f in ('osoby.py', 'strom.py', 'zaznamy.json', 'svazky.json', 'prepisy.json', 'zvyrazneni.json'): shutil.copy(out / 'data' / f, proj / 'data' / f)
        (proj / 'data' / 'import').mkdir(exist_ok=True); shutil.copy(out / 'data' / 'import' / 'gedcom.json', proj / 'data' / 'import' / 'gedcom.json')
        (proj / 'vyrezy').mkdir(exist_ok=True)
        for p in (out / 'vyrezy').glob('*.jpg'): shutil.copy(p, proj / 'vyrezy' / p.name)
        print(f'Zapsáno do {proj}/data a vyrezy.')


if __name__ == '__main__':
    main()
