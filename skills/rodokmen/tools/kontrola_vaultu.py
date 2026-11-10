#!/usr/bin/env python3
"""Kontrola soukromí před exportem na web. Selže (kód 1), pokud by se mohlo zveřejnit něco o žijícím člověku.
Použití: python3 -I kontrola_vaultu.py <vault> [podsložka, výchozí rodokmen]
Pravidla:
 - zveřejňuje se jen `verejne: true` (výchozí je neveřejné)
 - osoba bez úmrtí narozená před méně než 110 lety musí mít `soukromi: zijici`
 - `soukromi: zijici` nesmí být `verejne: true`
 - veřejná osoba musí mít doložené úmrtí / starý rok narození, nebo `soukromi: zemrely` (potvrdil člověk)
 - `verejne: omezene` (jen jméno a rok narození, pro žijící i zemřelé) smí mít jen pole z OK_KEYS
 - odkaz z těla veřejné poznámky na neveřejnou jen varuje (export ho nahradí obecným textem; vazby `father`, `mother`,
   `spouse`, `children` ve frontmatteru export u neveřejných osob vynechá)
"""
import re, sys, datetime, pathlib, yaml
LIMIT = 110
OK_KEYS = {'cr_type','cr_id','name','given_name','surnames','sex','born','soukromi','jistota','kekule','gedcom_id','verejne','tags','father','mother','father_id','mother_id','children','children_id','spouse','spouse_id'}
root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.') / (sys.argv[2] if len(sys.argv) > 2 else 'rodokmen')
year_now = datetime.date.today().year
def year(v):
    m = re.search(r'\d{4}', str(v or ''))
    return int(m.group()) if m else None
notes = {}
for p in root.rglob('*.md'):
    if '_plugin' in p.parts: continue
    t = p.read_text(encoding='utf-8')
    fm = {}
    m = re.match(r'---\n(.*?)\n---\n?(.*)', t, re.S)
    body = t
    if m:
        try: fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as e: print(f'CHYBA {p.name}: neplatné YAML ({e})'); sys.exit(1)
        body = m.group(2)
    notes[p.stem] = (p, fm, t)
errors, warns = [], []
def is_public(fm): return fm.get('verejne') is True
def is_limited(fm): return fm.get('verejne') == 'omezene'
for stem, (p, fm, t) in notes.items():
    if fm.get('cr_type') != 'person': continue
    pub, s = is_public(fm), fm.get('soukromi')
    b, died = year(fm.get('born')), fm.get('died')
    living = s != 'zemrely' and (not died) and b is not None and year_now - b < LIMIT
    unknown = (not died) and b is None
    rel = p.relative_to(root)
    if living and s != 'zijici': errors.append(f'{rel}: narozen {b} bez úmrtí – nastavit soukromi: zijici')
    if s == 'zijici' and pub: errors.append(f'{rel}: žijící osoba nesmí mít verejne: true')
    if pub and unknown and s != 'zemrely': errors.append(f'{rel}: veřejná osoba bez dat – doplnit úmrtí/narození, nebo soukromi: zemrely')
    if s == 'zijici' or is_limited(fm):
        extra = set(fm) - OK_KEYS
        if extra: (errors if (pub or is_limited(fm)) else warns).append(f'{rel}: omezená/žijící osoba má navíc pole {sorted(extra)}')
for stem, (p, fm, t) in notes.items():
    if not is_public(fm): continue
    body = re.sub(r'\A---\n.*?\n---\n?', '', t, count=1, flags=re.S)
    for link in set(re.findall(r'\[\[([^\]|#]+)', body)):
        tgt = notes.get(link.strip())
        if tgt and not is_public(tgt[1]):
            warns.append(f'{p.relative_to(root)}: tělo veřejné poznámky odkazuje na neveřejnou [[{link}]] (export nahradí)')
for w in warns: print('VAROVÁNÍ', w)
for e in errors: print('CHYBA', e)
print(f'{len(notes)} poznámek, {len(errors)} chyb, {len(warns)} varování')
sys.exit(1 if errors else 0)
