"""Test exportu z Obsidian vaultu (tools/export_z_vaultu.py): povolení `verejne`, soukromí žijících, brána kontroly.

Z kořene repozitáře:
  python3 -I tests/vault/test_export_z_vaultu.py skills/rodokmen
"""
import json, os, subprocess, sys, tempfile

SKILL = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "skills/rodokmen")
EXP = os.path.join(SKILL, "tools", "export_z_vaultu.py")
vysledky = []


def check(nazev, ok, detail=""):
    vysledky.append(bool(ok))
    print(f"[{'OK ' if ok else 'CHYBA'}] {nazev}{'' if ok else '  ' + str(detail)[:700]}", flush=True)


def osoba(vault, slug, **kw):
    fm = {"cr_type": "person", "cr_id": f"aaa-{abs(hash(slug)) % 1000:03d}-bbb-{len(slug):03d}", "name": slug.replace("-", " ").title(), "sex": "M",
          "jistota": "rodina", "verejne": False}
    fm.update(kw)
    lines = ["---"] + [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fm.items()] + ["---", f"# {fm['name']}", "", "## Co o osobě víme", "- narozen",
             "", "## Poznámky a rozpory", kw.pop("_text", "Poznámka.")]
    with open(os.path.join(vault, "rodokmen", "osoby", slug + ".md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def spust(*args):
    return subprocess.run([sys.executable, "-I", EXP, *args], capture_output=True, text=True)


with tempfile.TemporaryDirectory() as tmp:
    vault, web = os.path.join(tmp, "vault"), os.path.join(tmp, "web")
    os.makedirs(os.path.join(vault, "rodokmen", "osoby")); os.makedirs(os.path.join(web, "data"))
    osoba(vault, "koren-zijici", kekule=1, born=2000, soukromi="zijici", gedcom_id="@I1@",
          father='[[otec-zijici]]', mother='[[ded-novak]]')
    osoba(vault, "otec-zijici", kekule=2, born=1970, soukromi="zijici", gedcom_id="@I2@", children=["[[koren-zijici]]"])
    osoba(vault, "ded-novak", kekule=5, born=1900, died=1970, gedcom_id="@I3@", children=["[[koren-zijici]]"],
          jistota="doloženo")
    osoba(vault, "tajna-osoba", born=1990, soukromi="zijici", gedcom_id="@I4@")
    # 1) bez povolení nejde nic ven
    r = spust("--vault", vault, "--projekt", web)
    check("bez verejne: true/omezene export skončí s hláškou", r.returncode != 0 and "verejne" in (r.stdout + r.stderr), r.stdout + r.stderr)
    # 2) návrh a označení
    r = spust("--vault", vault, "--navrh")
    check("--navrh navrhne zemřelého jako true a žijícího předka jako omezene", "ded-novak" in r.stdout and "koren-zijici" in r.stdout and "tajna-osoba" not in r.stdout.split("bez dat")[0], r.stdout)
    r = spust("--vault", vault, "--oznacit")
    check("--oznacit proběhne", r.returncode == 0, r.stdout + r.stderr)
    # 3) export
    r = spust("--vault", vault, "--projekt", web)
    check("export projde", r.returncode == 0 and "Export OK" in r.stdout, r.stdout + r.stderr)
    out = os.path.join(web, "pracovni", "export_z_vaultu", "data")
    blob = "".join(open(os.path.join(dp, f), encoding="utf-8").read() for dp, _, fs in os.walk(out) for f in fs)
    snap = json.load(open(os.path.join(out, "import", "gedcom.json"), encoding="utf-8"))
    check("neveřejná žijící osoba není ve výstupu", "Tajna Osoba" not in blob and "@I4@" not in blob)
    check("žijící otec je jen omezený: bez poznámek a bez místa", snap["persons"]["@I2@"]["privacy_limited"] is True and "Poznámka." not in blob.split("Ded Novak")[0])
    check("žijící výchozí osoba je omezená (privacy_limited)", snap["persons"]["@I1@"]["privacy_limited"] is True)
    check("zemřelý předek je plný a má úmrtí", snap["persons"]["@I3@"]["privacy_limited"] is False and any(e["type"] == "DEAT" and e["owner"] == "@I3@" for e in snap["events"]))
    check("výchozí osoba je kekule 1", snap["root"] == "@I1@")
    check("rodina spojuje předka s dítětem", any("@I1@" in str(f) and "@I3@" in str(f) for f in snap["records"].values()), snap["records"])
    osoby_py = open(os.path.join(out, "osoby.py"), encoding="utf-8").read()
    check("osoby.py obsahuje P s kekule 1 a 5", "P = {1:" in osoby_py and " 5: " in osoby_py, osoby_py[:300])
    # 4) brána: žijící s verejne: true shodí kontrolu
    p = os.path.join(vault, "rodokmen", "osoby", "tajna-osoba.md")
    t = open(p, encoding="utf-8").read().replace("verejne: false", "verejne: true")
    open(p, "w", encoding="utf-8").write(t)
    r = spust("--vault", vault, "--projekt", web)
    check("žijící s verejne: true zastaví export", r.returncode != 0 and "kontrola" in (r.stdout + r.stderr).lower(), r.stdout + r.stderr)

print(f"\n{sum(vysledky)}/{len(vysledky)} v pořádku")
sys.exit(0 if all(vysledky) else 1)
