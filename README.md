# Smartdumbphone

Styr fra din pc, hvilke apps der findes på din OnePlus. Formålet er, at man ikke kan
hente Play Butik eller en browser frem og installere apps igen i et svagt øjeblik, når
man kun har telefonen i hånden.

## Sådan virker det

- **På telefonen** ligger en lille app uden knapper eller indstillinger. Den er sat
  som *device owner*, den rolle firmaer bruger til at styre arbejdstelefoner. Den gør
  kun, hvad pc'en beder om over USB-kablet:
  - skjuler eller viser apps
  - låser for installation, så intet kan installeres eller opdateres
  - spærrer for APK-filer, nye brugere og gæster, sikker tilstand og nulstilling via
    Indstillinger
  - blokerer interne browsere i apps (fx browseren i Messenger), så man ikke kan surfe
    eller se Reels den vej

  Android husker selv alle indstillingerne, så appen behøver ikke køre i baggrunden.
- **På pc'en** styrer du det hele fra et lille program med et vindue
  (`desktop\start.cmd`). Det taler med telefonen via adb over USB-kablet.

## Status

| Trin | Indhold | Status |
|---|---|---|
| 1 | Telefon-app + opsætningsguide | Klar til test: følg [docs/opsaetning.md](docs/opsaetning.md) |
| 2 | Pc-program med liste over apps og knapperne Lås / Åbn for installation | Klar til test: følg [docs/pc-program.md](docs/pc-program.md) |
| 5 | Blokering af interne browsere og Reels (fx i Messenger) | Klar til test: følg [docs/blokering.md](docs/blokering.md) |

## Mapper

| Mappe | Indhold |
|---|---|
| `android/` | Telefon-appen (Kotlin, Android Studio-projekt) |
| `desktop/` | Pc-programmet (Python): start med `start.cmd`. `sdp.cmd` er den lille kommandohjælper fra trin 1 |
| `docs/` | Guides på dansk |

## Det dækker løsningen ikke

- **Indbyggede browsere:** Browsere inde i apps, fx Messenger, kan stadig bruges til
  at surfe, men ikke til at installere apps.
- **Andre computere:** Enhver pc med adb, som du godkender på telefonen, kan styre
  den. I praksis er din pc og USB-kablet nøglen.
- **adb-apps på telefonen:** En adb-app på telefonen selv, fx Shizuku, LADB eller
  Termux, kan via "Trådløs fejlretning" gøre det samme som pc'en. Den kan også fjerne
  testversionen. Den slags apps skal derfor være skjult; `status` viser dem under
  `adbApps`.
- **Opdateringer:** Mens telefonen er låst, opdateres intet: hverken WebView,
  Google Play-tjenester, MitID eller bankapps. Åbn for installation og opdatér hver
  eller hver anden uge. Hav MitID-kodeviser, kodeoplæser eller chip som reserve.
- **Fabriksnulstilling:** En nulstilling via gendannelsestilstand (knapperne ved
  opstart) fjerner det hele.

## Vigtigt

- **Signeringsnøglen:** Appen bygges og signeres på din egen pc. Tag en kopi af
  `C:\Users\<dit navn>\.android\debug.keystore`. Uden den kan appen ikke opdateres
  (se guiden).
- **Ingen nøgler på GitHub:** Nøgler må aldrig lægges på GitHub. `.gitignore`
  udelukker dem.
- **Pakkenavnet:** Appens pakkenavn `io.github.tbmagi.smartdumbphone` må aldrig
  ændres.
