# Výkazy externistů – návrh aplikace

Stav: schváleno uživatelem 25. 10. 2026 včetně pravidla 14denního předstihu. Implementace dosud nezačala.

## Záměr a potvrzená zadání

Nahradit měsíční zasílání Excelů společnou webovou aplikací. Externisté zadávají práci a budoucí nepřítomnost, správce spravuje projekty, smluvní údaje a sleduje měsíční náklady. Historické výkazy lze importovat z Excelu.

Uživatel požaduje skutečný provoz, samostatnou aplikaci, vlastní databázi a hosting Railway. Překročení 8 hodin denně nebo smluvního měsíčního limitu musí zablokovat odeslání výkazu. Společný kalendář ukazuje nepřítomnost všech externistů.

Dodatečně potvrzeno uživatelem: nepřítomnost je nutné zadat nejpozději dva týdny předem.

Následující podrobnosti byly návrhové volby autora a jsou zahrnuté ve schváleném návrhu.

## Zvažované přístupy

- Samostatná aplikace a vlastní databáze: kontrola pravidel, přístupů a datového modelu; nutnost spravovat vydání a zálohování. Uživatel vybral tento přístup a Railway.
- Aplikace nad více spravovanými službami pro data a přihlášení: méně provozní práce, ale další poskytovatelé a jejich omezení. Nevybráno.

Technologický návrh autora: Python/Django, serverově vykreslované české rozhraní a PostgreSQL. Jedna aplikace a jedna databázová služba na Railway, bez samostatného JavaScriptového frontendu a bez fronty úloh v první verzi. Railway má dokumentovaný postup pro Django a PostgreSQL: https://docs.railway.com/guides/django.

## Rozsah první verze a přístupy

- Správce vytváří a deaktivuje účty, projekty a přiřazení externistů, nastavuje limity a sazby, prohlíží všechny výkazy a náklady, importuje historii a znovu otevírá odeslané výkazy k opravě.
- Externista pracuje pouze s vlastními výkazy a aktivními přiřazeními. Vidí společný kalendář, vytváří a mění vlastní nepřítomnosti. Nevidí cizí výkazy, sazby ani náklady.
- Není veřejná registrace. Přihlášení jménem/e-mailem a heslem, bezpečné relace. Správce může vydat jednorázový, časově omezený odkaz pro nastavení či obnovu hesla; distribuce odkazu probíhá mimo aplikaci. E-mailová služba není podmínkou první verze.
- Jeden zákazník/organizace; nejde o službu pro více nezávislých firem.

## Datový model

- Uživatel: identita, role, aktivita. Deaktivace zachovává historii.
- Projekt: název, identifikátor, aktivita. Historicky použitý projekt nelze tvrdě smazat.
- Přiřazení: externista, projekt, období oprávnění vykazovat práci.
- Smluvní podmínky pro přiřazení: platnost od/do, hodinová sazba, měsíční limit. Platnost je po celých kalendářních měsících a nesmí se překrývat. Limit je pro dvojici externista–projekt, nikoli společný rozpočet celého projektu. Pro jiný limit v konkrétním měsíci se vytvoří nové období podmínek. Bez podmínek nelze výkaz odeslat.
- Měsíční výkaz: externista, kalendářní měsíc, stav rozpracovaný/odeslaný, čas odeslání. Jeden výkaz zahrnuje všechny jeho projekty.
- Položka práce: datum, přiřazení/projekt, kladný počet celých minut a popis. UI přijímá hodiny včetně desetinného zápisu, převod musí být přesný na celé minuty. Více položek na stejném projektu a dni je dovoleno.
- Nepřítomnost: uživatel, první a poslední den včetně. Celodenní rozsahy, bez důvodu a zdravotních informací; vlastní překryvy se odmítají. Zadání budoucnosti, uplynulé záznamy zůstávají viditelné.
- Audit: kdo a kdy provedl odeslání, znovuotevření, změnu smluvních podmínek a import. Historické položky uchovávají použitou sazbu při odeslání/importu; běžná změna sazby minulost nepřepočítává.

Pro první verzi se navrhuje jediná měna CZK pro celou instalaci. Sazby a náklady používají přesná desetinná čísla, nikoli float. Časové pásmo Europe/Prague, datum práce se ukládá jako datum.

## Výkazy a tvrdé kontroly

Externista průběžně ukládá rozpracovaný výkaz a odesílá ho za celý kalendářní měsíc. Rozpracovaný výkaz může překračovat limit, aby bylo možné chyby postupně opravit; chybné datum, nekladný čas a cizí projekt se odmítají už při zápisu.

Při odeslání server uvnitř databázové transakce zkontroluje:

1. Součet všech položek osoby v každém dni přes všechny projekty nepřesáhne 480 minut.
2. Součet osoby na každém projektu v daném měsíci nepřesáhne příslušný smluvní limit. Rovnost je přípustná.
3. Každá položka má platné přiřazení a jednoznačné smluvní podmínky. Prázdný výkaz nelze odeslat.

Chyba uvede datum/projekt, vykázaný součet, limit a překročení; žádná část výkazu se neodešle. Kontrola zohlední také importovaná data. Souběžné změny a odesílání se serializují uzamčením výkazu; všechny cesty zápisu musejí respektovat tento zámek. Přímé volání serveru nesmí obcházet validaci.

Odeslané výkazy jsou zamčené. Správce je může s důvodem znovu otevřít, opravy podléhají stejným limitům. Neexistuje výjimka správce dovolující odeslat nadlimitní výkaz. Při znovuotevření se původní sazby zachovají pro opravu; případný výslovný přepočet podle opravených smluvních podmínek smí udělat správce a musí být auditovaný. Smluvní změny nesmějí tiše zneplatnit již odeslané výkazy.

Nepřítomnost sama o sobě práci neblokuje; požadavek se týká plánovacího kalendáře, ne schvalování volna.

## Náklady a přehledy

Správce vybere měsíc a vidí součet hodin a nákladů za projekt i rozpad po externistech. Náklad položky je počet minut / 60 × použitá hodinová sazba. Náklady se sečtou s vyšší přesností a výsledný součet za projekt/měsíc se zaokrouhlí na dvě desetinná místa běžným zaokrouhlením půl nahoru. Rozpracované částky jsou samostatně označený průběžný odhad; hlavní měsíční součet vychází z odeslaných výkazů a dokončených historických importů. Nejde o fakturaci, mzdy ani výpočet daní.

## Import historie

Správce nahraje .xlsx nebo CSV, namapuje sloupce datum, externista, projekt, hodiny a volitelný popis. Uživatelé, projekty a historické sazby/limity se nejprve založí; neznámé identity se nevytvářejí automaticky. Podpora starého binárního .xls není součástí návrhu.

Import má dva kroky: náhled s chybami a následné potvrzení přesně stejné dávky. Neukládá práci před potvrzením. Při potvrzení se znovu ověří současný stav databáze, smluvní podmínky i limity. Pravidla platí také pro historii; nadlimitní historii nelze importovat bez opravy.

Do měsíce s již existujícím výkazem se dávka odmítne sloučit; správce musí připravit úplný měsíc v jedné dávce. Import je atomický a vytváří zamčené historické výkazy. Kontroluje opakování souboru/dávky pomocí otisku souboru a vybraného listu (různé listy lze importovat samostatně) a upozorňuje na shodné řádky uvnitř dávky; shodný řádek vyžaduje opravu nebo výslovné potvrzení, protože dvě stejně dlouhé činnosti mohou být legitimní. Opakované potvrzení téže dávky nesmí vytvořit další výkazy.

Nahrazení existujícího měsíce není v první verzi; oprava probíhá znovuotevřením výkazu. Import nedůvěřuje klientským identifikátorům, nevyhodnocuje Excel vzorce a odmítá soubory s nezjištěnými hodnotami vzorců. Limit velikosti a počtu řádků chrání server; surové soubory nejsou trvale uchovávány. Připravená dávka a její obsah jsou v databázi s omezenou dobou platnosti.

## Společný kalendář

Měsíční a seznamový pohled se jmény a rozsahy nepřítomnosti všech aktivních i historicky relevantních externistů. Filtr podle člověka. Kalendář je přístupný pouze přihlášeným uživatelům. Správce může opravit záznam kohokoli, externista pouze svůj. Částečné dny a synchronizace s externími kalendáři se odkládají.

Začátek nepřítomnosti musí být nejméně 14 kalendářních dní po místním datu zadání v Europe/Prague; přesně 14 dní předem je přípustné. Například při zadání 1. listopadu je nejbližší povolený začátek 15. listopadu. Jde o kalendářní dny, nikoli pracovní dny nebo interval 336 hodin. Server odmítne pozdě zadanou nepřítomnost a sdělí nejbližší přípustné datum.

Schválená návrhová volba autora: při změně začátku či konce nepřítomnosti se 14denní předstih znovu ověří vůči dni změny a začátku výsledného rozsahu. Zrušení nepřítomnosti je možné i v kratší lhůtě. Správce nemá výjimku z předstihu při vytvoření nebo změně termínu. Pravidlo platí na serveru pro všechny cesty zápisu, nikoli jen v kalendářním formuláři.

## Provoz a zabezpečení

Produkční konfigurace Railway: aplikační služba, PostgreSQL s trvalým úložištěm, databáze přístupná aplikaci přes privátní síť. HTTPS, DEBUG vypnutý, explicitní povolené domény a CSRF origins, tajné klíče v proměnných prostředí. Migrace jako krok před vydáním, healthcheck a statické soubory nezávislé na vývojovém serveru. Žádné produkční údaje ani hesla v repozitáři.

Kontrola oprávnění na každém čtení i zápisu, CSRF, bezpečné cookies, omezení pokusů o přihlášení a nahrávání souborů. Testy zahrnou pokus číst/upravit cizí výkaz a získat cizí sazby.

Pro spuštění: vytvořit prvního správce bez výchozího veřejného hesla; nastavit zálohování PostgreSQL a ověřit obnovu do izolované databáze; ověřit přihlášení, limitní kontroly, import a přehledy na nasazené aplikaci. Přesná retence záloh a postup obnovy budou popsány v provozní dokumentaci. Nasazení závisí na dostupném přístupu k Railway a konfiguraci projektu; příprava aplikace sama neznamená provedené nasazení.

## Ověření a hranice první verze

Automatizované testy se zaměří na součty přes více projektů, hraničních 8 hodin, měsíční hranice, historické sazby, oprávnění, atomický import a souběžné zápisy. Integrace používá PostgreSQL, aby testovala skutečné zamykání. UI se ověří na běžném i mobilním rozměru a projde se celý tok externisty i správce.

Testy nepřítomnosti ověří přijetí přesně 14 dní předem, odmítnutí 13 dní předem, změnu termínu včetně změny pouze konce, přechod měsíce/roku a rozhodování podle místního data Europe/Prague kolem půlnoci a změn letního času.

Mimo rozsah: fakturace, více měn, veřejná registrace, schvalovací hierarchie, přílohy výkazů, e-mailové notifikace a propojení s účetnictvím. Konkrétní Excel soubory zatím nebyly poskytnuty; import proto zahrnuje mapování sloupců a vzorový soubor, nikoli garanci rozpoznání libovolného nestandardního sešitu.

Detaily rozvržení, knihovny pro tabulky/kalendář, názvy modelů a organizace modulů ponechány implementaci. Uživatel tento návrh schválil; následuje implementační plán.
