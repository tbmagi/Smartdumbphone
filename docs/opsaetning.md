# Opsætning af telefonen (trin 1)

Her sætter du telefon-appen op og tester, at den virker. Det tager 30-60 minutter.
Bagefter kan pc'en skjule apps og låse for installation. Pc-programmet med vindue og
knapper kommer i trin 2. Indtil da bruger du små kommandoer, som du kopierer ind.

**Du skal bruge:** din Windows-pc med Android Studio og GitHub Desktop, et USB-kabel og
telefonen.

**Godt at vide, før du starter**

- Telefonen bliver **ikke** nulstillet, og dine data bliver liggende.
- Du skal **fjerne alle konti** fra telefonen i et par minutter, fx Google, OnePlus og
  WhatsApp. Kontakter og kalender forsvinder fra telefonen, indtil du lægger
  Google-kontoen på igen. Så kommer de tilbage.
- **Betalingskort** i Google Wallet bliver fjernet, når Google-kontoen fjernes. Du skal
  tilføje dem igen bagefter, og banken beder dig bekræfte. Hav dit fysiske kort med i
  mellemtiden.
- Har du brugt **App cloner** (Parallelle apps), bliver de klonede apps slettet. Så
  længe appen styrer telefonen, kan App cloner og arbejdsprofiler ikke bruges.
- Har du en **arbejdsprofil** (fx Intune eller Company Portal), så stop og spørg mig
  først (se trin 5).
- Appen er en **testversion**. Alt kan fjernes igen fra pc'en (se
  [Nødudgang](#nødudgang-fjern-det-hele-igen)).

---

## 1. Tag backup

Der bør ikke forsvinde noget, men tag alligevel backup først:

- **Billeder:** Sæt telefonen til pc'en, vælg "Filoverførsel" på telefonen, og kopiér
  mappen `DCIM` til pc'en. Eller tjek, at Google Fotos har taget backup.
- **WhatsApp:** WhatsApp > Indstillinger > Chats > Sikkerhedskopiering > Sikkerhedskopier.

## 2. Hent koden og byg appen

1. Åbn GitHub Desktop, og vælg *File > Clone repository*. Vælg
   `tbmagi/Smartdumbphone`, og skriv **`C:\Smartdumbphone`** under *Local path*.
   Det skal være en kort mappe, der ikke ligger i OneDrive.
2. Klik på **Current branch** øverst, og vælg `claude/new-session-6zewu1`. Kan du ikke
   se den, så tryk først på *Fetch origin*. Tjek i Stifinder, at der nu er en mappe,
   der hedder `android`, i `C:\Smartdumbphone`.
3. Åbn Android Studio, vælg *File > Open*, og vælg mappen
   **`C:\Smartdumbphone\android`**.
   - Spørger den, om du stoler på projektet, så vælg **Trust Project**.
   - Kommer beskeden *"Please Select Gradle JVM to Import Project"*, så tryk
     **Use JVM 21**. Nyere Android Studio bruger Java 25, som projektets
     Gradle-version ikke kan køre med.
   - Foreslår den at opgradere "Android Gradle Plugin" eller Gradle, så vælg
     *Remind me later* eller *Don't ask for this project*. Projektet er sat op til de
     versioner, det har.
4. Vent, til Android Studio er færdig med at hente og indlæse projektet ("Gradle sync").
   Første gang tager det et par minutter. Hvis den spørger, om den skal installere en
   SDK-platform, så sig ja.
   - Fejler det med "Unsupported Java", så vælg *File > Settings > Build, Execution,
     Deployment > Build Tools > Gradle*, sæt *Gradle JDK* til en version 17 eller 21
     (vælg evt. *Download JDK*), og prøv igen.
5. Vælg *Build > Build App Bundle(s) / APK(s) > Build APK(s)*. I nyere versioner hedder
   det *Build > Generate App Bundles or APKs > Generate APKs*.
6. Når den er færdig, ligger appen her:
   `C:\Smartdumbphone\android\app\build\outputs\apk\debug\app-debug.apk`

> **Tag en kopi af signeringsnøglen.** Android Studio signerer appen med filen
> `C:\Users\<dit navn>\.android\debug.keystore`. Kopiér den til din USB-nøgle.
> Telefonen tager kun imod opdateringer af appen, der er signeret med præcis den
> samme fil. Mister du den, skal hele opsætningen laves om.

## 3. Gør adb klar

adb er det program, pc'en bruger til at tale med telefonen. Det følger med Android Studio.

**På pc'en:** Åbn PowerShell (eller Terminal), og skriv:

```powershell
cd C:\Smartdumbphone
$env:Path += ";$env:LOCALAPPDATA\Android\Sdk\platform-tools"
dir desktop\sdp.cmd
```

- Den anden linje gør, at du kan skrive `adb` i dette vindue. Den skal skrives igen,
  hver gang du åbner et nyt vindue.
- Den tredje linje skal vise filen `sdp.cmd`. Gør den ikke det, er du i den forkerte
  mappe.

Alle kommandoer i resten af guiden skrives i dette vindue.

**På telefonen:**

1. Gå til *Indstillinger > Om enheden > Version*, og tryk 7 gange på **Buildnummer**.
   Skriv din kode, hvis telefonen beder om den. Nu er Udviklerindstillinger slået til.
2. Søg efter **USB** i søgefeltet øverst i Indstillinger, og slå **USB-fejlretning** til.
   Den ligger under Udviklerindstillinger. Slå *ikke* "Trådløs fejlretning" til.
3. Sæt USB-kablet i. Hvis telefonen spørger, hvad USB skal bruges til, så vælg
   "Filoverførsel".

**Tjek forbindelsen:**

```powershell
adb devices
```

Telefonen spørger nu: *"Vil du tillade USB-fejlretning?"*. Sæt flueben i
*"Tillad altid fra denne computer"*, og tryk Tillad. Kør `adb devices` igen. Der skal
stå et serienummer efterfulgt af `device`.

Tjek også Android-versionen:

```powershell
adb shell getprop ro.build.version.release
adb shell getprop ro.build.display.id
```

Den første skal vise `14`. Skriv gerne begge svar ned til mig.

## 4. Installer appen

```powershell
adb install -t android\app\build\outputs\apk\debug\app-debug.apk
```

Der skal stå `Success`. `-t` er nødvendig, fordi det er en testversion.

**Hold øje med telefonen imens.** Kommer der en besked fra Play Protect eller telefonen
om installationen, så vælg *Installer alligevel* eller *Tillad*.

## 5. Fjern ekstra brugere

```powershell
adb shell pm list users
```

Der må kun stå én linje med `UserInfo{0:...}`.

- Står der også `UserInfo{999:...}`, er det App cloner. Fjern den med
  `adb shell pm remove-user 999`. Det sletter de klonede apps.
- **Står der "Work profile", "Arbejdsprofil" eller `1030` på en linje, så stop.** Det
  er en arbejdsprofil. Fjernes den, forsvinder alle arbejdsdata, og der kan ikke laves
  en ny, så længe appen styrer telefonen. Skriv til mig først.
- Står der andre numre, fx 10 eller 11 (gæst eller en anden bruger), fjerner du dem
  på samme måde: `adb shell pm remove-user 10`.

## 6. Fjern alle konti midlertidigt

1. Slå **Flytilstand** til, og lad den være slået til, indtil trin 7 er lykkedes. USB
   virker stadig. Ellers kan WhatsApp og lignende apps lægge deres konto på igen, når
   der kommer en besked.
2. Stop beskedapps, så de ikke starter af sig selv (det gør ikke noget, hvis du ikke
   har appen):

   ```powershell
   adb shell am force-stop com.whatsapp
   adb shell am force-stop org.telegram.messenger
   adb shell am force-stop org.thoughtcrime.securesms
   ```

3. Søg efter **Konti** i Indstillinger (på OxygenOS hedder det typisk
   *Brugere og konti*). Tryk på hver konto, og vælg *Fjern konto*. Det gælder Google,
   WhatsApp, Microsoft, Signal og alle andre. **OnePlus-kontoen** fjerner du ved at
   trykke på dit navn øverst i Indstillinger og vælge *Log ud*.
4. Tjek, at alle er væk:

   ```powershell
   adb shell "dumpsys account | grep Accounts:"
   ```

   Der skal stå `Accounts: 0`. Står der et højere tal, kan du se, hvilke konti der er
   tilbage, med:

   ```powershell
   adb shell "dumpsys account | grep 'Account {'"
   ```

   Kan du ikke finde en af dem under Konti, så send mig linjen med `type=`.

Åbn ikke andre apps, før du har lavet næste trin.

## 7. Gør appen til device owner

Kør tjekket fra trin 6 én gang til lige før, så du ved, at der stadig står
`Accounts: 0`. Derefter:

```powershell
adb shell dpm set-device-owner io.github.tbmagi.smartdumbphone/.AdminReceiver
```

Hvis det virker, står der `Success: Device owner set to package ...`. Hvis ikke:

| Fejlen indeholder | Hvad du gør |
|---|---|
| `already some accounts` | Der er stadig en konto. Gå tilbage til trin 6. Passer `Accounts: 0`, så genstart telefonen, **lås den op, og vent et minut**. Kør tjekket fra trin 6 igen, og prøv så igen. |
| `several users` | Der er stadig en ekstra bruger. Gå tilbage til trin 5. |
| `Unexpected @ProvisioningPreCondition` | OnePlus' egen spærring. Kopiér hele fejlbeskeden, læg kontiene på igen (trin 8), og send mig beskeden. Så går vi videre med plan B. |
| `already set` | Det er allerede gjort. Fortsæt med trin 8. |
| `being removed` | Vent 10 sekunder, og kør kommandoen igen. |
| `Unknown admin` | Appen er ikke installeret. Gå tilbage til trin 4. |
| Alt andet, fx `Can't set package` | Stop, og send mig hele fejlbeskeden. Læg kontiene på igen imens (trin 8). |

## 8. Læg kontiene på igen

Slå flytilstand fra. Søg efter **Konti** i Indstillinger, og vælg *Tilføj konto* for
Google og de andre. Log ind på OnePlus-kontoen igen, hvis du bruger den. Åbn WhatsApp
og de andre apps som normalt. Tilføj dine betalingskort i Google Wallet igen.

Telefonen viser nu en besked om, at *enheden administreres af din organisation*.
Det er bare vores app.

## 9. Test, at det virker

Du giver telefonen ordrer med den lille hjælper `desktop\sdp.cmd`. Hver kommando svarer
med en linje som `Result: Bundle[{json={"ok":true, ...}}]`.

1. **Status**

   ```powershell
   desktop\sdp status
   ```

   Der skal stå `"deviceOwner":true`. Åbn også appen **Smartdumbphone** på telefonen.
   Den viser det samme.

2. **Skjul og vis en app**

   ```powershell
   desktop\sdp hide com.android.chrome
   ```

   Chrome forsvinder fra telefonen. Hent den frem igen med:

   ```powershell
   desktop\sdp unhide com.android.chrome
   ```

   Ikonet kommer tilbage i app-oversigten. Du skal måske selv lægge det på
   startskærmen igen.

3. **Virker MitID og banken uden Play Butik og browser?** Dette er den vigtigste test.
   Skjul de tre apps, der skal være skjult til daglig:

   ```powershell
   desktop\sdp hide com.android.vending
   desktop\sdp hide com.android.chrome
   desktop\sdp hide com.google.android.googlequicksearchbox
   ```

   Prøv nu disse tre ting, og skriv ned, hvad der sker:
   - Godkend et MitID-login i MitID-appen, fx ved at logge ind på borger.dk på pc'en.
   - Log ind i din bankapp på telefonen.
   - Brug *Log på med MitID* inde i en app på telefonen, fx e-Boks eller MobilePay.
     Det er den, der oftest har brug for en browser.

   Vis derefter de tre apps igen:

   ```powershell
   desktop\sdp unhide com.android.vending
   desktop\sdp unhide com.android.chrome
   desktop\sdp unhide com.google.android.googlequicksearchbox
   ```

4. **Lås for installation**

   ```powershell
   desktop\sdp lock
   ```

   Svaret skal indeholde `"locked":true`. Tjek nu på telefonen:
   - Søg efter **Installer ukendte apps** i Indstillinger. Det skal være spærret af
     administratoren.
   - Søg efter **Nulstil**, og åbn siden med *Slet alle data* (gendan
     fabriksindstillinger). **Kig kun, og tryk ikke på nogen nulstil-knap.** *Slet alle
     data* skal være grå eller vise, at administratoren har spærret den. Er den ikke
     spærret, så stop og skriv til mig. "Nulstil netværk" og "Nulstil alle
     indstillinger" er ikke spærret, og det er meningen.

   Prøv også at installere appen igen fra pc'en. Det skal **fejle** med en besked om
   "restricted" eller "User restriction":

   ```powershell
   adb install -r -t android\app\build\outputs\apk\debug\app-debug.apk
   ```

5. **Åbn for installation igen**

   ```powershell
   desktop\sdp unlock
   ```

   Svaret skal indeholde `"locked":false` og `"protected":true`.

6. **Genstart telefonen**, lås den op, og kør `desktop\sdp status` igen. Alt skal være
   som før.

**Fortæl mig bagefter:** om trin 7 virkede, hvad der skete i test 3, og om noget
opførte sig mærkeligt.

---

## Når testen er god: lås telefonen

Hvis alt i test 3 virkede, så kør:

```powershell
desktop\sdp hide com.android.vending
desktop\sdp hide com.android.chrome
desktop\sdp hide com.google.android.googlequicksearchbox
desktop\sdp status
```

Linjerne skjuler Play Butik, Chrome og Google-appen, som også indeholder Assistent og
Lens. Se så på svaret fra `status`:

- **`"visibleBrowsers"`** skal være `[]`. Står der andre browsere, fx Firefox eller
  Edge, så skjul hver af dem med `desktop\sdp hide <pakkenavn>`.
- **`"adbApps"`** skal være `[]`. Står der en app, fx Shizuku eller Termux, kan den
  styre telefonen ligesom pc'en. Skjul den på samme måde.

Har du Gemini eller Google Lens som separate apps, kan du også skjule
`com.google.android.apps.bard` og `com.google.ar.lens`. Får du svaret "Der er ingen
app med pakkenavnet", har du ikke den app. Til sidst:

```powershell
desktop\sdp lock
```

**Hvis noget i test 3 ikke virkede:**

- Hvis det kun virkede, når **Play Butik** var synlig, så spring den første hide-linje
  over. Play Butik er så synlig, men den kan ikke installere noget, mens telefonen er
  låst.
- Hvis *Log på med MitID* kun virkede, når **Chrome** var synlig, så lås ikke endnu, og
  skriv til mig. Så laver jeg en løsning, hvor Chrome er synlig, men kun kan åbne
  MitID og din banks sider.

## Når du vil installere eller opdatere apps

Gør det hver eller hver anden uge, så WebView, Google Play-tjenester, MitID og
bankapps bliver opdateret:

```powershell
desktop\sdp unlock
desktop\sdp unhide com.android.vending
```

Åbn Play Butik, og vælg *Profil > Administrer apps og enhed > Opdater alle*. Vent, til
der står, at alle apps er opdaterede. Bagefter:

```powershell
desktop\sdp hide com.android.vending
desktop\sdp status
desktop\sdp lock
```

Tjek i svaret fra `status`, at `"visibleBrowsers"` og `"adbApps"` stadig er `[]`.

> Mens telefonen er låst, kan MitID-appen eller bankappen kræve en opdatering og holde
> op med at virke, indtil du har åbnet for installation fra pc'en. Hav MitID-kodeviser,
> kodeoplæser eller chip som reserve.

## Alle kommandoer

| Kommando | Hvad den gør |
|---|---|
| `desktop\sdp status` | Viser tilstand, skjulte apps, synlige browsere og adb-apps |
| `desktop\sdp list` | Viser alle apps på telefonen. Listen er lang og er mest til pc-programmet i trin 2 |
| `desktop\sdp hide PAKKE` | Skjuler en app helt. Virker kun for apps med ikon og for browsere |
| `desktop\sdp unhide PAKKE` | Viser en app igen |
| `desktop\sdp lock` | Låser: intet kan installeres eller opdateres |
| `desktop\sdp unlock` | Åbner for installation. Beskyttelsen forbliver slået til |
| `desktop\sdp release JA` | Fjerner det hele igen (se nedenfor) |

**Beskyttelsen**, som er slået til fra første `lock` eller `unlock`, spærrer for:

- installation af APK-filer, fx fra Filer, Messenger eller mails
- nye brugere og gæster
- sikker tilstand
- *Slet alle data* via Indstillinger

## Opdatering af appen senere

Telefonen skal være åben for installation, og appen skal være bygget på samme pc
(med samme `debug.keystore`):

```powershell
desktop\sdp unlock
adb install -r -t android\app\build\outputs\apk\debug\app-debug.apk
desktop\sdp lock
```

## Nødudgang: fjern det hele igen

```powershell
desktop\sdp release JA
adb uninstall io.github.tbmagi.smartdumbphone
```

Det viser alle skjulte apps igen, fjerner alle spærringer og gør appen til en
almindelig app, som derefter afinstalleres. Står der
`DELETE_FAILED_DEVICE_POLICY_MANAGER`, så vent 10 sekunder, og kør `adb uninstall`-linjen
igen.

Hvis appen ikke svarer, kan pc'en altid fjerne den direkte, fordi det er en testversion:

```powershell
adb shell dpm remove-active-admin io.github.tbmagi.smartdumbphone/.AdminReceiver
adb uninstall io.github.tbmagi.smartdumbphone
```

Tjek bagefter, at Play Butik og Chrome er tilbage. Er de ikke, så skriv til mig.

Vil du sætte appen op igen bagefter, skal du fjerne alle konti igen (trin 6).

## Hvis noget går galt

- **`adb devices` viser `unauthorized`:** Lås telefonen op, og tryk Tillad i
  beskeden om USB-fejlretning.
- **`adb devices` viser ingenting:** Prøv et andet kabel eller USB-stik, og vælg
  "Filoverførsel" på telefonen. Åbn *Enhedshåndtering* på pc'en. Står telefonen med et
  gult udråbstegn, så installer *Google USB Driver* (Android Studio > *Tools > SDK
  Manager > SDK Tools*), og sæt kablet i igen.
- **`desktop\sdp` giver "not recognized":** Du er ikke i mappen `C:\Smartdumbphone`.
  Skriv `cd C:\Smartdumbphone`.
- **Svaret siger `Kun adb (pc'en) må styre telefonen`:** Det burde ikke ske, når du
  bruger `desktop\sdp`. Send mig hele linjen.
- **Svaret siger `Error while accessing provider`:** Appen er ikke installeret, eller
  telefonen er ikke låst op efter en genstart.
- **Svaret siger `har ikke noget ikon i app-oversigten`:** Appen kan ikke skjules,
  fordi den er en del af systemet. Det er en sikring, så telefonen ikke går i stykker.
