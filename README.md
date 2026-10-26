# Výkazy

Česká webová aplikace pro projektové výkazy externistů, kontrolu smluvních limitů,
měsíční náklady, import historie a plánování nepřítomnosti.

## Co aplikace umí

- Vlastní účty externistů, role správce, jednorázové odkazy pro nastavení hesla.
- Měsíční výkaz napříč projekty, průběžné ukládání a zamčení po odeslání.
- Serverově vynucený denní limit 8 hodin celkem a smluvní měsíční limit osoby na projektu.
- Sazby platné po měsících, historické snímky sazeb a náklady projektů v Kč.
- Excel `.xlsx` a CSV: přiřazení sloupců, kontrola, náhled a atomický import celých měsíců.
- Společný kalendář a celodenní nepřítomnosti se začátkem nejméně 14 kalendářních dní předem.

## Lokální spuštění

Vyžaduje Python 3.13, [uv](https://docs.astral.sh/uv/) a PostgreSQL 14 nebo novější.
Docker Compose používá PostgreSQL 17. Produkce nepoužívá SQLite.

```sh
uv sync --frozen
cp .env.example .env
```

V `.env` nastavte `SECRET_KEY` (vygenerujte `uv run python -c 'import secrets; print(secrets.token_urlsafe(64))'`),
`DATABASE_URL` na lokální databázi, `DEBUG=1`, `ALLOWED_HOSTS=localhost,127.0.0.1` a
`CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000`.
Soubor `.env` je ignorovaný a aplikace ho sama nenačítá; exportujte jeho hodnoty:

```sh
set -a
. ./.env
set +a
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py collectstatic --noinput
uv run python manage.py runserver
```

Otevřete `http://localhost:8000`. První správce nemá žádné sdílené výchozí heslo.

Alternativa s Dockerem: přidejte do `.env` i náhodné `POSTGRES_PASSWORD` (pro Compose
použijte heslo bez znaků vyžadujících URL escaping), pak:

```sh
docker compose up -d db
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
docker compose up -d web
```

## První nastavení a měsíční práce

1. Správce v **Lidé a přístupy** vytvoří účty. Tlačítkem **Odkaz k heslu** vydá odkaz
   platný 24 hodin, který předá příslušné osobě bezpečným kanálem. Aplikace zprávy neposílá.
2. V **Projekty a smlouvy** vytvoří projekt s unikátním kódem, přiřadí externistu
   a zadá sazbu a měsíční limit hodin. Smluvní období se zadává prvním dnem měsíce;
   koncový měsíc je zahrnut a období jednoho přiřazení se nesmějí překrývat.
3. Externista otevře vlastní výkaz pro požadovaný měsíc a zapisuje datum, projekt,
   hodiny a popis. Desetinné hodiny lze zadat s tečkou i čárkou; čas musí odpovídat
   celým minutám (např. `1,5` = 90 minut).
4. Při odeslání se zkontroluje celý měsíc. Denní součet přes všechny projekty nesmí
   přesáhnout 8 hodin a měsíční součet na projektu smluvní limit. Rovnost je dovolena.
   Koncept může chyby obsahovat, odeslat jej ale nelze. Správce nemá výjimku z limitů.
5. Odeslaný výkaz se zamkne. Správce jej může s důvodem vrátit k opravě; opravy znovu
   podléhají limitům. Běžná změna sazby nepřepočítává odeslanou historii. Výslovný
   přepočet sazeb je dostupný pouze správci u rozpracovaného výkazu a je auditovaný.
6. **Náklady projektů** ukazují odeslané výkazy a odhady konceptů odděleně.
   Chybějící sazba znamená neúplný odhad. Projektový součet se zaokrouhluje až na konci.

Deaktivace účtu/projektu zachová historii. Aplikace nemá veřejnou registraci ani
obecné administrační rozhraní, které by umožnilo obejít doménová pravidla.

## Historické soubory

Vzor: [examples/history.csv](examples/history.csv), také ke stažení v aplikaci.

```csv
Datum;Externista;Projekt;Hodiny;Popis
2026-09-01;jana;WEB;1,5;Analýza požadavků
```

Před importem založte identity, projekty, přiřazení a sazby/limity platné pro dané
historické měsíce. Externistu identifikuje uživatelské jméno nebo e-mail, projekt
jeho unikátní kód. CSV v UTF-8 může mít BOM a oddělovač čárka, středník nebo tabulátor.
Datum může být `RRRR-MM-DD`, `DD.MM.RRRR` nebo Excel datum se správným formátem buňky.

Importujte kompletní měsíc osoby (včetně všech projektů) v jedné dávce. Existující
měsíce se neslučují ani nepřepisují. Na historii platí stejné limity jako na nové
výkazy. Dávka s jakoukoli chybou se vůbec neuloží. Shodné řádky vyžadují výslovné
potvrzení; opakovaný import téhož dokončeného souboru/listu se odmítne. Různé listy stejného
sešitu lze importovat postupně, pokud nezasahují do již existujících měsíců.

Maximum: 5 MiB, 10 000 řádků, 60 sloupců, 50 MiB rozbaleného XLSX obsahu. Pokud má
sešit více listů, zadejte název listu. Staré `.xls` ani makra nejsou podporované.
Vzorce se nevyhodnocují; potřebují uložený výsledek. V případě chyby v Excelu vložte
hodnoty, uložte sešit a nahrajte jej znovu. Surové soubory se trvale neukládají.
Náhled má platnost 24 hodin. Po dokončení se řádky odstraní, zůstává otisk a audit.

## Nepřítomnost

Kalendář je společný a dostupný jen po přihlášení. Externista spravuje své záznamy,
správce může spravovat všechny. Nepřítomnost je celodenní včetně obou krajních dnů.
Začátek musí být nejméně **dnešek + 14 kalendářních dní v Europe/Prague**; pravidlo
platí i při změně začátku nebo konce a také pro správce. Například 1. listopadu lze
zadat začátek nejdříve 15. listopadu. Zrušení je možné kdykoliv. Vlastní překryvy
nejsou dovolené, soukromý důvod se nezadává. Nepřítomnost sama neblokuje vykazování.

## Ověření

Testovací uživatel PostgreSQL musí smět vytvářet testovací databáze. Použijte
lokální/testovací `DATABASE_URL`, nikdy produkční údaje.

```sh
uv run playwright install chromium
uv run ruff check .
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py collectstatic --noinput
uv run pytest
```

Playwright testuje přihlášení, správu smluv, odeslání, limity, import, náklady a
kalendář, včetně mobilního rozměru. Na macOS může použít nainstalovaný Chrome.
Testovací hook pouze pro E2E umožňuje synchronní Django ORM vedle interní smyčky
Playwright; produkční prostředí tuto výjimku nenastavuje. Souběžné zápisy se testují
na PostgreSQL pomocí nezávislých spojení. Screenshoty jsou v `artifacts/qa/`.

## Railway

Konfigurace je v `Dockerfile` a `.railway/railway.ts`. Migrace se spouštějí před vydáním,
Gunicorn obsluhuje požadavky, WhiteNoise statické soubory. `/health/` kontroluje
připojení k databázi. Kompletní nasazení, zálohy a obnova: [docs/operations.md](docs/operations.md).

Omezení první verze: jedna organizace a CZK, bez fakturace, e-mailových notifikací,
schvalovacích hierarchií a synchronizace s externími kalendáři. Nasazení a ověření
obnovy na konkrétním Railway projektu vyžadují přístup k danému projektu.
