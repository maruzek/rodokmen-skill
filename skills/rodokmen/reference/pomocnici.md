# Pomocníci: Opus řídí, levný model čte (pravidla, limity)

Platí pro velká kola čtení matrik a knih (stovky snímků). Zkušenost uživatele z testů (10. 11. 2026): **GPT-6.1 Terra**
čte staré matriky stabilně a dobře za zlomek ceny; **Claude Opus 5.5** je hlavní model, rozhoduje, ověřuje a zapisuje.

## Role
- **Opus (hlavní sezení):** plán kola, zadání, kontrola výsledků, ověření čtení na snímku, zápis do vaultu/dat, komunikace
  s uživatelem. Nic z toho nedeleguješ.
- **Terra (pomocníci):** projdou přidělené snímky, přečtou zápisy, najdou hledané záznamy, vrátí přepis a jistotu.
  Zapisují jen do `pracovni/pom_<id>/vysledky.md` (nikdy do `data/` ani vaultu).
- Kde Terra není k dispozici, použij levnější Claude pomocníky (SKILL.md → Pomocníci (subagenti)) jen se souhlasem
  uživatele. Nikdy se tiše nepřepínej na jiného poskytovatele ani model.

## Jak je pustit (T3 Code)
1. Jednou za konverzaci zavolej `orchestrator_capabilities` a ověř, že je k dispozici `gpt-6.1-terra` (poskytovatel `codex`).
   Chybí-li, řekni to a zeptej se, co dál. Neptej se, zda se má model použít, pokud uživatel už Terru zvolil.
2. Spouštěj přes `delegate_task` (`target.provider = codex`, `model = gpt-6.1-terra`, `reasoningEffort`: výchozí **low**;
   `medium` pro špatně čitelné knihy po zkoušce; vyšší nepoužívej bez souhlasu). Více pomocníků = více volání, každý
   dostane svůj úsek (svazek, rozsah snímků).
3. Dávky a čekání řeš nástroji T3 (`next` od delegáta); žádné pollování.

## Limity (výchozí, uživatel je může změnit)
Před každým velkým kolem **napiš uživateli plán s čísly** a počkej na schválení:
- max **3 pomocníci současně** (tvrdý strop 5), max **40 snímků na pomocníka**, max **150 snímků za kolo**;
- jeden pokus na dávku, **žádné automatické opakování** neúspěšných dávek v cyklu; opakuj jen s úpravou zadání;
- po kole zapiš do `poznamky/denik-hledani.md` (nebo `research_log.md`): kolik snímků, kolik pomocníků, kolik přečteno.
- **Kredity:** při prvním spuštění v konverzaci se zeptej, zda má uživatel dost kreditů u GPT/Codexu. Při jakékoli chybě
  typu limit, kredity, kvóta, rate limit, platba, přihlášení **okamžitě skonči**, nic neopakuj, nespouštěj jiné
  placené modely a řekni to uživateli. Nikdy nepokračuj „na přečerpání“ ani nepřepínej na jiné předplatné.
- Dej přednost kratším dávkám: neúspěch stojí méně.

## Zadání pomocníkovi (šablona)
Obsahuje jen to, co potřebuje, **žádné osobní údaje uživatele ani rodiny** (jen příjmení, obec, roky hledaných záznamů
z dávné minulosti), žádný e-mail, žádné údaje o žijících:
- cesta k snímkům (soubory ve `pracovni/`), který svazek a rozsah, koho/co hledat (příjmení, obce, roky);
- formát výsledku po snímcích: snímek, zápis č., typ (N/O/Z), datum, jména, rodiče/svědci, **přepis doslova**, jistota
  (jisté / nejisté / nečitelné), a **co skutečně přečetl** (rok a první jméno na snímku) i u prázdných snímků;
- „Neviděl jsem“ je platný výsledek. Nic nedomýšlet, nevyplňovat chybějící slova, nespojovat osoby.

## Ověření (vždy)
Každý nález, který jde do vaultu, ověří Opus sám na snímku (`tools/overit.py`, `tools/vyrez.py`) před tím, než dostane
`stav_cteni: potvrzeno` nebo `jistota: doloženo`. Neověřené čtení zůstává `pracovní` a jde do `ukoly.md`. U dvou rodin
stejného jména ve vsi ověřuj souvislosti (rodiče, děti, čp.). Pomocník nemá kontext celého stromu.
