# Výkazy externistů – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task, or superpowers:subagent-driven-development if the user chooses that execution method. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zprovoznit českou aplikaci pro vlastní výkazy externistů, blokování nadlimitních výkazů, projektové náklady, import historie a společný kalendář na Railway.

**Architecture:** Serverově vykreslovaná Django aplikace, jedna PostgreSQL databáze. Doménové zápisy procházejí transakčními službami; běžná administrativa nesmí obcházet jejich pravidla. Oddělené moduly pro účty, smlouvy, výkazy, import a kalendář.

**Tech Stack:** Python 3.13, Django 5.2 LTS s aktuální opravnou verzí, psycopg 3, Gunicorn, WhiteNoise, openpyxl, django-axes; pytest-django a Playwright pro ověření. Závislosti uzamknout v uv.lock; PostgreSQL 17 pro lokální a CI integraci. Bez produkční SQLite a bez externích JS/CDN závislostí.

**Spec:** `docs/superpowers/specs/2026-10-25-time-reports-design.md` (schváleno 25. 10. 2026).

## Global Constraints

- Samostatná aplikace, vlastní databáze a hosting Railway; žádná veřejná registrace.
- Denní součet osoby přes všechny projekty nejvýše 480 minut; měsíční limit pro dvojici externista–projekt; rovnost přípustná, bez výjimky správce.
- Odeslání za celý kalendářní měsíc; koncept může překročit limit, odeslaný výkaz je zamčený.
- Celé minuty, kladný čas; přesné desetinné sazby; jediná měna CZK; výsledný součet za projekt/měsíc na dvě desetinná místa metodou půl nahoru.
- Datum práce je datum; časové pásmo Europe/Prague. Nepřítomnost začíná nejdříve místní dnešek + 14 kalendářních dní, včetně při změně termínu; zrušení dovoleno kdykoli.
- Externista nevidí cizí výkazy, sazby ani náklady; společný kalendář pouze pro přihlášené, bez důvodů nepřítomnosti.
- Import .xlsx/CSV: mapování, náhled, potvrzení, stejná limitní pravidla, atomický zápis; nevytváří automaticky identity a neslučuje existující měsíce.
- Tajné hodnoty mimo repozitář; zabezpečené produkční nastavení, zálohy a ověření obnovy před skutečným spuštěním.
- Neimplementovat fakturaci, více měn, veřejnou registraci, schvalovací hierarchii, přílohy, e-mailové notifikace ani propojení s účetnictvím.
- Adresář zatím není Git repozitář. Bez požadavku uživatele nevytvářet commity; po každém úkolu zapsat výsledek ověření do `docs/implementation-progress.md`.

## Review Focus

1. Dva souběžné požadavky na úpravu/odeslání/import nesmějí obejít limity nebo vytvořit duplicitní měsíc (úkoly 2, 4).
2. Změna historických podmínek nesmí tiše změnit již vykázané náklady ani zneplatnit odeslaný výkaz (úkoly 1–3).
3. Podvržené ID uživatele, výkazu, projektu či dávky nesmí zpřístupnit cizí data (úkoly 1, 2, 4, 5).
4. České desetinné čárky, Excel data, chybějící hodnoty vzorců a opakované řádky musejí mít srozumitelný výsledek bez částečného importu (úkol 4).
5. Pravidlo předstihu musí používat pražské datum i kolem půlnoci, změn času a konce měsíce/roku (úkol 5).

## Společné rozhraní a soubory

- `config/settings.py`, `config/urls.py`, `config/wsgi.py`: konfigurace, hlavní routy, produkční vstup.
- `common/permissions.py`: `require_manager(user) -> None`, `require_owner_or_manager(actor, owner_id) -> None`; neaktivní uživatel nesmí provádět zápisy. Správce je aktivní `is_staff`, nikoli libovolná oprávnění z formuláře.
- `accounts/`: vlastní User od první migrace, přihlášení, jednorázové odkazy, správa účtů.
- `contracts/`: Project, Assignment, ContractTerms a služby pro jejich změny.
- `reports/`: MonthlyReport, TimeEntry, audity, zápisy, odeslání a nákladové přehledy.
- `imports/`: ImportBatch, parsování, náhled a potvrzení.
- `calendar_app/`: Absence, validace, kalendář a formuláře.
- `templates/`, `static/app.css`: společný český design, navigace, stavy a responzivní rozvržení.
- `tests/`: testy doménových služeb, HTTP oprávnění a PostgreSQL transakcí; `tests/e2e/` pro prohlížeč.
- `Dockerfile`, `compose.yaml`, `railway.json`, `.env.example`, `.github/workflows/ci.yml`, `README.md`, `docs/operations.md`: reprodukovatelné spuštění, ověření a provoz.

Vzájemné datové rozhraní: Assignment odkazuje na uživatele a projekt; ContractTerms má `start_month`, `end_month` (včetně, nullable), `hourly_rate`, `monthly_limit_minutes`. MonthlyReport má unikátní `(user, month)` s měsícem vždy prvního dne, stav `draft/submitted`, `submitted_at`. TimeEntry má `report`, `assignment`, `date`, `minutes`, `description`, nullable `rate_snapshot`. AuditEvent ukládá aktéra, akci, objekt, čas a metadata bez hesel/tokenů.

### Task 1: Účty, smlouvy a provozovatelný základ

**Files:** `pyproject.toml`, `uv.lock`, `.python-version`, `manage.py`, `config/*`, `common/permissions.py`, `accounts/{models,forms,services,views,urls}.py`, `contracts/{models,forms,services,views,urls}.py`, úvodní migrace, `templates/{base,registration/*,contracts/*,accounts/*}`, `static/app.css`, `compose.yaml`, `tests/test_accounts.py`, `tests/test_contracts.py`.

**Interfaces:** Produces `terms_for(assignment, month) -> ContractTerms`, `save_terms(*, actor, terms) -> ContractTerms`, `issue_setup_link(*, actor, user, request) -> str`; `User`, `Project`, `Assignment`, `ContractTerms`. Smluvní měsíce se nepřekrývají, sazba nezáporná, limit kladný; přiřazení má platnost v datech. Změny podmínek zamykají osobu a ověřují dotčené odeslané výkazy pomocí doménového validátoru z úkolu 2.

- [x] Vytvořit testy `test_contractor_cannot_manage_accounts_or_terms`, `test_setup_link_expires_and_is_single_use`, `test_deactivated_user_cannot_login`, `test_overlapping_terms_rejected`, `test_inactive_project_preserves_history`, `test_retroactive_limit_change_cannot_invalidate_submitted_report`. Pro autentizaci otestovat jméno i unikátní e-mail, CSRF a omezení opakovaných pokusů.
- [x] Spustit `uv run pytest tests/test_accounts.py tests/test_contracts.py -q`; nejprve ověřit selhání kvůli chybějící funkcionalitě, nikoli nesprávné konfiguraci databáze.
- [x] Připravit Django, PostgreSQL, uvedené modely/služby a jejich správcovské formuláře. Jednorázový odkaz použije Django token generator, životnost 24 hodin a zneplatnění po změně hesla. Nový účet bez použitelného hesla; žádné automatické odesílání zpráv. Obcházející přímé admin zápisy nepovolit.
- [x] Doplnit audit smluvních změn a test pro souběžné zakládání překrývajících se podmínek; serializovat podle osoby v jednotném pořadí osoba → výkaz → položka. Mezizávislý test historických výkazů dokončit s úkolem 2.
- [x] Spustit stejné testy, `uv run python manage.py check` a migrace na čistém PostgreSQL. Zapsat výsledky do `docs/implementation-progress.md`.

### Task 2: Zápis práce a neobejitelné limitní kontroly

**Files:** `reports/{models,forms,services,validation,views,urls}.py`, migrace, `templates/reports/{list,detail,entry_form}.html`, `tests/test_reports.py`, `tests/test_concurrency.py`.

**Interfaces:** Consumes modely/služby úkolu 1. Produces `save_entry(*, actor, report_id, assignment_id, date, minutes, description, entry_id=None) -> TimeEntry`, `delete_entry(*, actor, entry_id) -> None`, `validate_report(report) -> list[ReportIssue]`, `submit_report(*, actor, report_id) -> MonthlyReport`, `reopen_report(*, actor, report_id, reason) -> MonthlyReport`. `ReportIssue` obsahuje kód, českou zprávu, datum/projekt, součet, limit a překročení; neúspěšné odeslání vyvolá doménovou validační chybu. Všechny mutace včetně vytvoření měsíce získávají stejný zámek osoby a výkazu.

- [x] Napsat testy: `test_480_minutes_allowed`, `test_481_minutes_across_projects_blocks_whole_submission`, `test_monthly_exact_limit_allowed`, `test_monthly_limit_exceeded_blocks_submission`, `test_missing_terms_and_empty_report_rejected`, `test_wrong_month_or_assignment_rejected`, `test_submitted_entries_locked`, `test_reopen_requires_manager_and_reason`. Ověřit `status == 'draft'` a žádné snímky sazeb po neúspěchu.
- [x] Ověřit selhání přes `uv run pytest tests/test_reports.py -q` a implementovat doménové služby, formuláře a české obrazovky. Decimal hodiny přijmout s tečkou i čárkou; hodnoty neodpovídající celým minutám odmítnout. Datum práce musí být v měsíci výkazu a období přiřazení; nové zápisy nepřijímat na neaktivní projekt/přiřazení.
- [x] Při úspěšném odeslání atomicky uložit snímky sazeb, stav a audit. Při opětovném otevření zachovat dřívější snímky; nová položka použije podmínky svého měsíce. Doplnit `reprice_report(*, actor, report_id, reason) -> MonthlyReport` jako výslovnou auditovanou operaci pouze pro rozpracovaný výkaz a správce.
- [x] Napsat HTTP testy `test_forged_report_id_cannot_read_or_write`, `test_contractor_cannot_reopen_or_reprice`, `test_csrf_required_for_mutations`; zkontrolovat i seznamy, odkazy a chybové stránky na únik dat.
- [x] Použít PostgreSQL a dvě nezávislá spojení ve `test_edit_racing_submit_keeps_submitted_report_valid`, `test_concurrent_month_creation_unique`, `test_terms_change_racing_submit_serialized`. Spustit `uv run pytest tests/test_reports.py tests/test_contracts.py tests/test_concurrency.py -q`, zapsat výsledek.

### Task 3: Měsíční projektové náklady

**Files:** `reports/costs.py`, doplnění `reports/{views,urls}.py`, `templates/reports/costs.html`, `tests/test_costs.py`.

**Interfaces:** `monthly_costs(*, actor, month) -> list[ProjectCost]`; ProjectCost zahrnuje projekt, minuty a CZK celkem i rozpad po lidech, samostatně potvrzené hodnoty a odhady konceptů. Sazby ze snímků pro historii, podmínky pro nové koncepty; chybějící sazba znamená neúplný odhad, nikoli nulové náklady.

- [x] Testy `test_project_total_uses_each_person_rate`, `test_drafts_separate_from_submitted`, `test_rate_change_preserves_historical_cost`, `test_round_only_project_total_half_up`, `test_missing_rate_marks_estimate_incomplete`, `test_costs_forbidden_to_contractor`. Konkrétní příklad: 90 minut při 800 Kč/h + 60 minut při 1000 Kč/h = 2200,00 Kč.
- [x] Spustit `uv run pytest tests/test_costs.py -q` a ověřit očekávaná selhání.
- [x] Implementovat agregaci v Decimal s dostatečnou přesností a konečným `quantize(Decimal('0.01'), ROUND_HALF_UP)`. Přidat výběr měsíce, projektové karty/tabulku a rozpad po lidech, včetně prázdného stavu.
- [x] Spustit stejné testy a zaznamenat výsledky.

### Task 4: Import historie s náhledem a atomickým potvrzením

**Files:** `imports/{models,parsers,services,forms,views,urls}.py`, migrace, `imports/management/commands/purge_expired_imports.py`, `templates/imports/{upload,mapping,preview,result}.html`, `examples/history.csv`, `tests/test_imports.py`, rozšíření `tests/test_concurrency.py`.

**Interfaces:** `parse_upload(file, mapping) -> ParsedUpload`, `prepare_batch(*, actor, file, mapping) -> ImportBatch`, `confirm_batch(*, actor, batch_id, accept_duplicates=False) -> ImportResult`. Dávka uchovává normalizovaná data, vlastníka, SHA-256 souboru, mapování, expiraci 24 hodin a stav. Výsledek uvádí počty a chyby podle řádků. Využívá validátor výkazů a snímkování sazeb z úkolu 2.

- [x] Napsat testy `test_preview_writes_no_reports`, `test_invalid_row_rolls_back_entire_batch`, `test_confirm_revalidates_changed_terms`, `test_confirm_twice_is_idempotent`, `test_existing_month_rejected`, `test_daily_limit_across_import_projects`, `test_expired_or_foreign_batch_rejected`, `test_unknown_identity_rejected`.
- [x] Přidat parser testy pro českou čárku, ISO a české datum, Excel datum, UTF-8 BOM a oddělovač čárka/středník; vzorec bez cached value odmítnout. CSV bere externistu jako unikátní username nebo e-mail a projekt jako unikátní kód, nikoli databázové ID či nejednoznačné jméno. Prázdné řádky ignorovat, čas 0/záporný/necelé minuty odmítnout.
- [x] Spustit `uv run pytest tests/test_imports.py -q`; ověřit selhání a implementovat .xlsx/CSV parser, mapování podle hlaviček, náhled a oprávnění. U .xlsx nabídnout list, pokud jich je více; nikdy tiše nevynechat ostatní listy.
- [x] Omezit vstup na 5 MiB, 10000 datových řádků a rozbalený XLSX archiv na 50 MiB, odmítnout .xls a makra. Shodné řádky vyžadují explicitní potvrzení; shodný otisk již dokončené dávky odmítnout. Surový soubor neukládat; normalizované řádky po dokončení odstranit, ponechat audit/otisk.
- [x] Implementovat potvrzení v jedné transakci: uzamknout dávku a všechny osoby v seřazeném pořadí, odmítnout existující měsíce, znovu validovat, vytvořit všechny výkazy jako odeslané se sazbami. Expirace se kontroluje při použití, příkaz purge maže neplatný obsah i bez scheduleru.
- [x] Ověřit `test_duplicate_rows_require_explicit_confirmation`, `test_oversized_or_zip_bomb_upload_rejected`, `test_concurrent_import_and_manual_month_creation_atomic`. Spustit `uv run pytest tests/test_imports.py tests/test_concurrency.py -q`; zaznamenat výsledek a připravit vzorový CSV s vysvětlivkami v README.

### Task 5: Společný kalendář s 14denním předstihem

**Files:** `calendar_app/{models,forms,services,views,urls}.py`, migrace, `templates/calendar_app/{calendar,list,form}.html`, `tests/test_absences.py`.

**Interfaces:** `save_absence(*, actor, user_id, start, end, absence_id=None) -> Absence`, `delete_absence(*, actor, absence_id) -> None`. Čistý validátor `validate_absence_dates(*, start, end, today) -> None`; produkční služba mu vždy předá `timezone.localdate()`, nikdy klientské dnešek. Zamykání osoby serializuje kontrolu překryvů.

- [x] Testy `test_exactly_14_calendar_days_allowed`, `test_13_days_rejected`, `test_edit_end_also_rechecks_notice`, `test_cancellation_allowed_inside_notice`, `test_manager_has_no_notice_override`, `test_overlap_and_reversed_range_rejected`, `test_contractor_cannot_edit_other_absence`.
- [x] Přidat testy s kontrolovaným časem kolem pražské půlnoci, změn letního času a přelomu roku. Potvrdit, že se porovnávají datumy, nikoli 336 hodin. Spustit `uv run pytest tests/test_absences.py -q` a ověřit selhání.
- [x] Implementovat službu a zobrazení. Měsíční mřížka s vícedenními nepřítomnostmi, přepínání měsíců, seznam a filtr osoby; historie se zachová. Formulář ukazuje nejbližší přípustné datum. Žádné pole pro soukromý důvod, serverové oprávnění u všech mutací.
- [x] Spustit stejné testy, včetně souběžného vytvoření překrývajících se rozsahů; zapsat výsledek.

### Task 6: Produkční balení, celková kontrola a Railway

**Files:** `Dockerfile`, `.dockerignore`, `railway.json`, `.env.example`, `.github/workflows/ci.yml`, `README.md`, `docs/operations.md`, `tests/test_deployment.py`, `tests/e2e/test_user_journeys.py`, finální úpravy `config/settings.py` a `static/app.css`.

**Interfaces:** `/health/` provede jednoduchý databázový dotaz a vrátí 200 jen při připravenosti, jinak 503 bez detailu chyby. Docker image spouští Gunicorn na Railway PORT, statické soubory jsou součástí image. Pre-deploy příkaz `python manage.py migrate --noinput`, healthcheck `/health/`.

- [ ] Napsat `test_production_requires_secrets_and_database`, `test_health_checks_database`, `test_production_cookie_and_csrf_settings` a E2E průchody: správce založí účet/projekt/podmínky; externista zadá 8 h a odešle; 8 h 1 min se neodešle; náklady odpovídají; import projde náhledem/potvrzením; kalendář přijme 14 dní a odmítne 13 dní. Ověřit přístup cizím účtem a po odhlášení.
- [ ] Spustit a ověřit selhání testů; implementovat produkční nastavení bez skrytých fallbacků na SQLite/DEBUG/default secret. Explicitní domény, HTTPS/cookies a CSRF, proxy trust pouze pro Railway, omezení uploadů, rotace přihlašovacích relací a throttling pomocí django-axes.
- [ ] Připravit Docker build, CI s PostgreSQL a přesné kroky Railway: služby, privátní DATABASE_URL, SECRET_KEY, domény/CSRF, pre-deploy, první správce a vydání jednorázových odkazů. CI: `uv sync --frozen`, `uv run python manage.py makemigrations --check --dry-run`, `uv run pytest`, prohlížečové testy. Nezaměnit deploy healthcheck s průběžným monitoringem.
- [ ] Dokumentovat denní zálohy s 7denní retencí a týdenní s 4týdenní retencí, ověřit dostupnost v konkrétním Railway plánu a podle ní nastavit ekvivalentní zálohování; ukázat `pg_dump -Fc` a obnovu pomocí `pg_restore` do oddělené databáze. Ověřit obnovené počty, výkazy, náklady a přihlášení; žádný test obnovy přes produkční data. Konkrétní dostupnost zálohování ověřit v aktuální oficiální dokumentaci před nasazením.
- [ ] Spustit plnou sadu na PostgreSQL, `uv run python manage.py check --deploy` s produkčními testovacími proměnnými, migrace na prázdné DB, Docker build a E2E na desktopu i mobilní šířce. Otevřít screenshoty a opravit přetečení/chybějící stavy. Zaznamenat skutečné příkazy a výsledky.
- [ ] Provést bezpečnostní a závěrečné review podle příslušných skills, opravit zjištění a zopakovat pouze dotčené kontroly.
- [ ] Je-li dostupné autorizované Railway připojení, nasadit a ověřit celý kritický tok a obnovu. Jinak dodat aplikaci s přesným seznamem dosud neprovedených provozních kroků a požádat pouze o chybějící přístup; netvrdit, že je produkce nasazena. Žádné zprávy externistům neposílat.

## Kontrola pokrytí a předání

Úkol 1 pokrývá účty a časové smluvní podmínky, úkol 2 zápisy a limity, úkol 3 náklady a historii sazeb, úkol 4 historický import, úkol 5 kalendář a předstih, úkol 6 produkční bezpečnost, přenositelnost a provozní ověření. Všech pět Review Focus bodů má přiřazený test. Testy transakcí nikdy nenahrazovat SQLite; chybějící lokální PostgreSQL řešit lokálním serverem nebo Dockerem.

Ověřené podklady: Django 5.2 podporuje Python 3.13 a je LTS (https://docs.djangoproject.com/en/5.2/releases/5.2/). Railway pre-deploy běží v odděleném kontejneru a změny souborů nepřenáší do aplikace (https://docs.railway.com/deployments/pre-deploy-command); collectstatic proto patří do buildu. Healthcheck slouží k přepnutí provozu při vydání, ne k průběžnému monitorování (https://docs.railway.com/deployments/healthchecks).

Návrh způsobu realizace: implementovat postupně v této relaci bez paralelních implementátorů; části sdílejí stejné modely a transakční služby. Nezávislé závěrečné review lze provést dle příslušného skillu. Způsob realizace a plán se před zahájením implementace předkládají uživateli.
