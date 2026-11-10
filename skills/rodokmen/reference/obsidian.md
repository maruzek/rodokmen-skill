# Režim „vault“ (Obsidian jako zdroj pravdy)

Používá se, když rodokmen žije v Obsidian vaultu a repo projektu (`data/`, `web/`) slouží jen pro veřejný web.
**Poznáš to tak:** ve vaultu existuje `rodokmen/CLAUDE.md` a `_nastroje/kontrola_soukromi.py` (nebo uživatel řekl, že
zdrojem pravdy je vault). Pak platí tento návod a `data/` projektu **needituješ** (je výstupem exportu, viz níže).

## 1. Přečti nejdřív
`<vault>/rodokmen/CLAUDE.md` (pravidla vaultu, jsou nadřazená tomuto návodu), `rodokmen/poznamky/ukoly.md` (co čeká na
schválení) a `rodokmen/poznamky/migrace.md` (v jakém stavu je převod). Cesta k vaultu z WSL:
`/mnt/c/Users/<uživatel>/Obsidian/Vaults/<vault>/<vault>`. Obsidian nemusí běžet, soubory jsou obyčejné `.md`.

## 2. Struktura (`rodokmen/`)
`osoby/` (jedna osoba = jeden soubor), `rodiny/` (prosté poznámky), `zdroje/svazky/`, `zdroje/zapisy/<klic>/` (složka na zápis:
`<klic>.md` + `<klic>.jpg` výřez), `zdroje/knihy/`, `udalosti/`, `mista/`, `poznamky/`, `instituce/`, `_plugin/` (nesahej).
Šablony: `_sablony/rodokmen/`. Nástroje: `_nastroje/` (`crid.py`, `kontrola_soukromi.py`).

## 3. Pravidla zápisu
- **Identifikátory:** `cr_id` je v tvaru `aaa-000-aaa-000` a vždy se počítá `_nastroje/crid.py` z čitelného klíče
  (`osoba_<slug_s_podtržítky>`). `gedcom_id` a `kekule` se nikdy nemění.
- **Jistota** (`jistota`): doloženo, pravděpodobné, rodina, cizí-strom, hypotéza, neznámé. **Čtení** (`stav_cteni`): pracovní,
  potvrzeno. Čtení od pomocníka je vždy `pracovní`, dokud ho nepřečteš sám na snímku (`pomocnici.md`).
- **Žádné slučování osob** a žádné hádání příbuzenských vazeb. Nejisté ztotožnění = poznámka v `poznamky/` s důvody,
  ne spojení. Stejná jména v různých letech jsou běžná past.
- **Žijící lidé:** jen jméno a rok narození, `soukromi: zijici`, nikdy `verejne: true`. Úmrtí potvrzuje jen uživatel.
- **Výchozí `verejne: false`.** Veřejné je jen to, co uživatel výslovně schválil.
- **Pluginové průvodce Charted Roots** („Post-Import Cleanup Wizard“ → Apply fixes) nespouštět, poškozuje data.
- `migrace_osoby.py` nepouštět znovu (přepíše ruční opravy; vyžaduje `--force`). Jednorázové opravy dělej novým skriptem
  nebo přímo úpravou poznámky, pokaždé s komentářem „Opravy podle nálezů (datum)“ a zdrojem.
- Obrázky: výřezy zápisů, max. asi 1800 px, JPEG ~0,3–0,5 MB, pojmenované po zápisu. Celé stránky ne, kromě
  citovaných stran knih (kopie jen pro osobní použití, soukromé).
- Nesahej do `.obsidian/`. Pracuj ve větvi vaultu (`git checkout -b <téma>`) a po kroku commit; na `main` se slučuje
  fast-forwardem po `kontrola_soukromi.py` bez chyb.

## 4. Postup při přidání zápisu z matriky
1. Složka `zdroje/zapisy/<klic>/` s `<klic>.md` (šablona `zapis`) a výřezem `<klic>.jpg` (`tools/vyrez.py`, pak zmenšit).
2. Přepis, překlad, `stav_cteni: pracovní`, odkaz na svazek a snímek (citace až na snímek).
3. Osoby: úprava existující poznámky (odkaz na zápis, nová fakta) nebo nová osoba (cr_id přes `crid.py`).
4. Do `poznamky/denik-hledani.md` řádek (co, kde, výsledek); co potřebuje rozhodnutí, do `poznamky/ukoly.md`.
5. `python3 -I _nastroje/kontrola_soukromi.py .` musí vyjít bez chyb.

## 5. Export na web (fáze 5): `tools/export_z_vaultu.py`
Nástroj ze skillu generuje z poznámek vaultu soubory, které čte `tools/export_web.py` (`data/osoby.py`, `zaznamy.json`,
`svazky.json`, `prepisy.json`, `strom.py`, `import/gedcom.json`, výřezy). `data/` v repu webu je pak jen výstup a **needituje se**.
```
python3 -I SKILL_DIR/tools/export_z_vaultu.py --vault <vault> [--slozka rodokmen] [--projekt <web>] --navrh | --oznacit | (export) | --zapsat
```
- Jde ven jen `verejne: true` (zemřelé osoby, zápisy) a `verejne: omezene` (jen jméno a rok narození, i pro žijící).
  Výchozí je `false`. Žijící osoba nikdy `true`.
- Postup: `--navrh` (jen výpis) → **souhlas uživatele** → `--oznacit` → export do `<web>/pracovni/export_z_vaultu/` → kontrola výstupu →
  `--zapsat` → `npm run data` a `npm run build` v `web/`. Nasazení webu jen na výslovný pokyn (`reference/web.md`).
- Export se zastaví, když kontrola soukromí hlásí chybu (použije `<vault>/_nastroje/kontrola_soukromi.py`, nemá-li vault vlastní,
  tak `tools/kontrola_vaultu.py`) nebo když se ve výstupu objeví jméno neveřejné žijící osoby.

## 6. Formát poznámek, na který se nástroj spoléhá
- Osoba: `cr_type: person`, `name`, `born`/`died` (ISO, `ABT rok`, nebo rok), `kekule` (jen přímí předci), `gedcom_id` (nepovinné),
  `father`/`mother`/`spouse`/`children` jako `[[odkaz]]`, `jistota`, `soukromi` (`zijici`/`zemrely`), `verejne`, volitelně `varovani:` (seznam).
  Tělo: sekce `## Co o osobě víme` (odrážky → fakta), další sekce (kromě Původ, Zdroj, Citace z exportu, Příbuzenství) → poznámka.
- Zápis: `cr_type: source`, `klic` (klíč zápisu s podtržítky), `source_parent` (poznámka svazku), `snimek`, `druh` (N/O/Z/…),
  `source_repository_url`, `title`; v těle `**Datum zápisu:**`, sekce `Přepis originálu`, `Český překlad / vysvětlení`, `Co zápis dokládá`;
  výřez `<poznámka>.jpg` ve stejné složce.
- Svazek: `title`, `repository`, `portal`, `source_repository_url`, v těle `**Popis:**`.
- Výchozí osoba webu je `kekule: 1` a musí být `verejne: true` nebo `omezene`.
Test: `python3 -I tests/vault/test_export_z_vaultu.py skills/rodokmen`.
