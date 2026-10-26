# Provoz aplikace na Railway

## Vytvoření služeb a první vydání

1. V Railway vytvořte projekt a PostgreSQL službu s persistentním volume. Databázi
   nevystavujte veřejně, pokud nepotřebujete dočasný přístup pro konkrétní údržbu.
2. Přidejte aplikační službu z tohoto zdrojového kódu (GitHub nebo Railway CLI).
   Repozitář zatím není připojen ke GitHubu. Instalujte SDK `npm ci --prefix .railway`,
   propojte CLI s projektem a spusťte `railway config plan`, pak po kontrole
   `railway config apply --yes`. `.railway/railway.ts` spravuje pouze část `web`,
   volí Dockerfile, před vydáním spouští `python manage.py migrate --noinput` a čeká
   na `/health/`. Nastavení je nutné aplikovat přes CLI; samotný upload kódu ho neaplikuje.
   Databázi, volume a tajné proměnné tato část nespravuje. Staré railway.json/toml
   nové služby nenačítají a jejich podpora končí 1. 12. 2026.
3. Nastavte proměnné aplikace:
   - `DATABASE_URL=${{Postgres.DATABASE_URL}}` (název služby upravte podle projektu;
     použijte interní adresu z privátní sítě, nikoli veřejný TCP proxy URL).
   - `SECRET_KEY`: náhodná hodnota alespoň 50 znaků, bez sdílení v repozitáři.
   - `DEBUG=0`.
   - `ALLOWED_HOSTS`: vlastní doména a/nebo vygenerovaná Railway doména, bez schématu,
     oddělené čárkou, bez wildcard a bez mezer.
   - `CSRF_TRUSTED_ORIGINS`: tytéž originy se schématem `https://`, oddělené čárkou.
   - `PORT` přiděluje Railway. `DJANGO_ALLOW_ASYNC_UNSAFE` v produkci **nenastavujte**.
4. Vygenerujte veřejnou HTTPS doménu pro aplikaci a vložte ji do proměnných.
   Doména `healthcheck.railway.app` se přidává automaticky kvůli platformnímu healthchecku.
5. Nasaďte. Chybná migrace zablokuje vydání; statické soubory vznikají již při buildu,
   protože pre-deploy kontejner nepřenáší změny souborů do aplikačního kontejneru.
6. Prvního správce lze vytvořit při startu pomocí jednorázových proměnných
   `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`.
   Nastavte všechny tři před vydáním; Docker spustí `bootstrap_admin --if-configured`.
   Příkaz nezmění existujícího správce, při souběžném prvním startu se stejnými údaji
   je idempotentní. Po úspěšném vytvoření všechny tři proměnné odstraňte a ověřte
   další start. Heslo se nikdy nevypisuje do logů. Alternativně v interaktivním
   shellu aplikace spusťte `python manage.py createsuperuser`.
   Zadejte vlastní unikátní jméno, e-mail a bezpečné heslo. Žádný účet se při buildu
   nevytváří. Lokální `railway run` nemusí mít přístup k privátní databázové adrese;
   pro tento krok použijte shell běžící v Railway privátní síti (např. Railway SSH).
7. Ověřte přihlášení, vytvoření externisty, nastavení hesla, projekt/podmínky,
   zamítnutí 8 h + 1 min, přijetí 8 h, náklady, import a 14denní předstih nepřítomnosti.
8. V prostředí služby spusťte `python manage.py check --deploy`; výstup má být bez
   varování. Ověřte rovněž domény, cookies, CSRF a neprůchodnost nepřihlášeného přístupu.

Aplikace důvěřuje `X-Forwarded-Proto` od Railway proxy. Nedávejte před ni proxy, která
propouští libovolnou klientskou hodnotu tohoto headeru. Omezení přihlášení používá
Django Axes, jméno i transportní IP; při blokaci více lidí za společnou proxy může
správce použít `python manage.py axes_reset` v důvěryhodném shellu. Nenastavujte
neověřené `X-Forwarded-For` jako důvěryhodnou klientskou IP. Uploady a odkazy pro
nastavení hesla mají další databázové limity.

## Pravidelná údržba

- Denně spustit `python manage.py purge_expired_imports` (Railway cron nebo shell).
  Vypršelé dávky se odmítají i bez úklidu, příkaz odstraňuje jejich obsah.
- Pravidelně aktualizovat opravné verze závislostí, po změně uzamknout `uv.lock`
  a spustit CI. Django používá podporovanou řadu 5.2 LTS.
- Hlídání chyb v logách a externí HTTPS monitoring nastavte samostatně. Railway
  deployment healthcheck **není průběžný monitoring**.
- Aplikační audit uchovává smluvní změny, odeslání, znovuotevření a importy. Přístup
  do databáze je správcovský, audit nenahrazuje ochranu proti přímým zásahům DBA.

## Zálohy

Před skutečným spuštěním nakonfigurujte zálohy PostgreSQL volume v Railway a ověřte
jejich dostupnost i cenu pro svůj plán. Cíl je denní záloha se 7denní retencí a
4 týdenní zálohy; pokud platformní retence tento cíl nekryje, přidejte plánovaný
logický dump do odděleného soukromého úložiště s odpovídající retencí. Zálohy nejsou
nastavené samotným `.railway/railway.ts`, nastavení patří ke službě/volume.

Logický dump PostgreSQL (proměnná `DATABASE_URL` z bezpečného prostředí, nevkládat
heslo přímo do historie příkazů):

```sh
umask 077
pg_dump --dbname="$DATABASE_URL" --format=custom --no-owner --no-acl --file=time-reports.dump
```

Použijte klienta `pg_dump` stejné nebo novější hlavní verze než server. Dump uchovává
osobní i smluvní data; ukládejte jej šifrovaně mimo aplikační službu a neposílejte ho
mailem. Ověřte počet úspěšných záloh a upozornění na chybějící dump.

## Ověření obnovy bez zásahu do produkce

Vytvořte **novou izolovanou databázi**. `RESTORE_DATABASE_URL` musí ukazovat právě na
ni; nemá to být aktuální produkční URL. Příkazy nepoužívají `--clean`:

```sh
pg_restore --dbname="$RESTORE_DATABASE_URL" --no-owner --no-acl --exit-on-error time-reports.dump
DATABASE_URL="$RESTORE_DATABASE_URL" python manage.py migrate --check
DATABASE_URL="$RESTORE_DATABASE_URL" python manage.py check
```

Na izolované instanci aplikace porovnejte počty uživatelů, smluv, výkazů, položek a
nepřítomností. Pro vybraný odeslaný měsíc porovnejte součty hodin, sazby a náklady.
Ověřte přihlášení izolovaným správcem a zobrazení kalendáře. Zapište datum obnovy,
zdrojový dump, výsledky kontrol a dobu obnovy. Zkoušku opakujte po změně databázové
verze a alespoň jednou za čtvrtletí.

## Vadné vydání

V Railway lze vrátit předchozí aplikační vydání; tento krok nevrací databázové
migrace ani data. Před potenciálně nevratnou migrací pořiďte ověřenou zálohu.
Obnovu produkce provádějte až podle konkrétního incidentu, se zachováním současného
stavu pro rozbor; tento dokument žádnou produkční obnovu automaticky neprovádí.

## Referenční dokumentace

- [Django na Railway](https://docs.railway.com/guides/django)
- [Pre-deploy příkazy](https://docs.railway.com/deployments/pre-deploy-command)
- [Deployment healthcheck](https://docs.railway.com/deployments/healthchecks)
- [Railway volume backups](https://docs.railway.com/volumes/backups)

## Stav konkrétní instalace

Projekt: `czechitas-time-reports`, adresa https://web-production-b2fec.up.railway.app.
Railway API odmítlo nastavení denních/týdenních záloh: tyto funkce jsou dostupné
pouze pro Pro workspace. Automatické zálohy proto zatím nejsou nakonfigurované;
čeká se na rozhodnutí vlastníka o Pro nebo samostatném soukromém úložišti.
Přechod tarifu se neprovádí automaticky.
