# Ověření implementace

- PostgreSQL 17: 66 testů prošlo bez varování, včetně souběžných zápisů a tří celých uživatelských postupů v prohlížeči.
- Ruff: zdrojové soubory zformátované; finální lint se spouští před předáním.
- `makemigrations --check --dry-run`: žádné chybějící migrace.
- Docker: sestavení úspěšné, migrace na čisté databázi úspěšné; healthcheck, HTTPS proxy, CSP, X-Frame-Options a manifestové CSS ověřeny v běžícím produkčním obrazu.
- `check --deploy`: bez připomínek.
- Závislosti: pip-audit nenašel známé bezpečnostní chyby v instalovaných závislostech.
- Obnova: skutečný PostgreSQL17 dump obnoven do oddělené databáze; ověřeny identity, smlouvy, odeslaný výkaz, historická sazba, nepřítomnost, přihlášení a náklad 800 Kč.
- Nezávislé review: bez zjištěného obcházení oprávnění, limitů, transakčních pravidel nebo historie nákladů. Dva krajní vstupy opraveny s testy RED→GREEN: extrémní číselný exponent a různé listy stejného sešitu.
- Vizuální kontrola: desktop a mobilní šířka 390 px, styly ověřeny i automaticky. Mobilní odhlášení ověřeno regresním testem.

Screenshoty jsou lokálně v `artifacts/qa/`. Detailní záznam rozhodnutí a skutečných příkazů je v `docs/implementation-progress.md`.

Railway: aplikace nasazena na https://web-production-b2fec.up.railway.app. Ověřeno skutečné HTTPS přihlášení správce, všechny hlavní obrazovky, statické soubory, CSRF i odhlášení. Jednorázové BOOTSTRAP_ADMIN_* proměnné odstraněny a následný start a přihlášení znovu ověřeny. Databáze je připojena privátní sítí.

Automatické cloudové zálohy dosud nejsou aktivní: Railway API je pro tento workspace odmítlo jako funkci tarifu Pro. Čeká se na volbu vlastníka mezi Pro/native zálohami a samostatnými automatickými zálohami do soukromého úložiště. Obnova byla zatím ověřena na izolované lokální PostgreSQL17 databázi, nikoli pomocí Railway volume snapshotu.

Poslední ověřené samostatné vydání: `047ecf02-31f7-4c06-8a37-bac199fc9fc8` (SUCCESS), následná HTTPS kontrola opět úspěšná.
