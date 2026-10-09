# Opsætning af telefonen (trin 1)

Her sætter du telefon-appen op og tester, at den virker. Det tager 30-60 minutter.
Bagefter kan pc'en skjule apps og låse for installation. Pc-programmet med vindue og
knapper kommer i trin 2. Indtil da bruger du små kommandoer, som du kopierer ind.

**Du skal bruge:** din Windows-pc med Android Studio, et USB-kabel og telefonen.

**Godt at vide, før du starter**

- Telefonen bliver **ikke** nulstillet, og dine data bliver liggende.
- Du skal **fjerne alle konti** fra telefonen i et par minutter, fx Google, OnePlus og
  WhatsApp. Kontakter og kalender forsvinder fra telefonen, indtil du lægger
  Google-kontoen på igen. Så kommer de tilbage.
- Har du brugt **App cloner** (Parallelle apps), bliver de klonede apps slettet.
- Appen er en **testversion**. Alt kan fjernes igen fra pc'en (se
  [Nødudgang](#nødudgang-fjern-det-hele-igen)), så du kan ikke låse dig selv ude.

---

## 1. Tag backup

Der bør ikke forsvinde noget, men tag alligevel backup først:

- **Billeder:** Sæt telefonen til pc'en, vælg "Filoverførsel" på telefonen, og kopiér
  mappen `DCIM` til pc'en. Eller tjek, at Google Fotos har taget backup.
- **WhatsApp:** WhatsApp > Indstillinger > Chats > Sikkerhedskopiering > Sikkerhedskopier.

## 2. Byg appen

1. Hent koden fra GitHub til din pc, fx med GitHub Desktop (*File > Clone repository*).
   Indtil koden er flettet ind i `main`, ligger den på branchen
   `claude/new-session-6zewu1`.
2. Åbn Android Studio, vælg *File > Open*, og vælg mappen **`android`** inde i repoet.
3. Vent, til Android Studio er færdig med at hente og indlæse projektet ("Gradle sync").
   Første gang tager det et par minutter. Hvis den spørger, om den skal installere en
   SDK-platform, så sig ja.
4. Vælg *Build > Build App Bundle(s) / APK(s) > Build APK(s)*. I nyere versioner hedder
   det *Build > Generate App Bundles or APKs > Generate APKs*.
5. Når den er færdig, ligger appen her i repoet:
   `android\app\build\outputs\apk\debug\app-debug.apk`

> **Tag en kopi af signeringsnøglen.** Android Studio signerer appen med filen
> `C:\Users\<dit navn>\.android\debug.keystore`. Kopiér den til din USB-nøgle.
> Telefonen tager kun imod opdateringer af appen, der er signeret med præcis den
> samme fil. Mister du den, skal hele opsætningen laves om.

## 3. Gør adb klar

adb er det program, pc'en bruger til at tale med telefonen. Det følger med Android Studio.

**På pc'en:** Åbn PowerShell (eller Terminal), og gå til mappen med repoet, fx:

```powershell
cd "$env:USERPROFILE\Documents\GitHub\smartdumbphone"
$env:Path += ";$env:LOCALAPPDATA\Android\Sdk\platform-tools"
```

Den anden linje gør, at du kan skrive `adb` i dette vindue. Den skal skrives igen,
hver gang du åbner et nyt vindue.

**På telefonen:**

1. Gå til *Indstillinger > Om enheden > Version*, og tryk 7 gange på **Buildnummer**.
   Skriv din kode, hvis telefonen beder om den. Nu er Udviklerindstillinger slået til.
2. Søg efter **USB-fejlfinding** i søgefeltet øverst i Indstillinger, og slå det til.
3. Sæt USB-kablet i. Hvis telefonen spørger, hvad USB skal bruges til, så vælg
   "Filoverførsel".

**Tjek forbindelsen:**

```powershell
adb devices
```

Telefonen spørger nu: *"Vil du tillade USB-fejlfinding?"*. Sæt flueben i
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

## 5. Fjern ekstra brugere

```powershell
adb shell pm list users
```

Der må kun stå én linje med `UserInfo{0:...}`.

- Står der også `UserInfo{999:...}`, er det App cloner. Fjern den med
  `adb shell pm remove-user 999`. Det sletter de klonede apps.
- Står der andre numre, fx 10 eller 11 (gæst eller en anden bruger), fjerner du dem
  på samme måde: `adb shell pm remove-user 10`.

## 6. Fjern alle konti midlertidigt

1. Søg efter **Konti** i Indstillinger (på OxygenOS hedder det typisk
   *Brugere og konti*).
2. Tryk på hver konto, og vælg *Fjern konto*. Det gælder Google, OnePlus/HeyTap,
   WhatsApp, Microsoft, Signal og alle andre.
3. Tjek, at alle er væk:

   ```powershell
   adb shell "dumpsys account | grep Accounts:"
   ```

   Der skal stå `Accounts: 0`. Står der et højere tal, kan du se, hvilke konti der er
   tilbage, med:

   ```powershell
   adb shell "dumpsys account | grep 'Account {'"
   ```

Åbn ikke andre apps, før du har lavet næste trin. Nogle apps, fx WhatsApp, lægger
selv deres konto på igen, når de bliver åbnet.

## 7. Gør appen til device owner

```powershell
adb shell dpm set-device-owner io.github.tbmagi.smartdumbphone/.AdminReceiver
```

Hvis det virker, står der `Success: Device owner set to package ...`. Hvis ikke:

| Fejlen indeholder | Hvad du gør |
|---|---|
| `already some accounts` eller `Can't set package` | Der er stadig en konto. Gå tilbage til trin 6. Hvis `Accounts: 0` passer, så genstart telefonen og prøv igen. |
| `several users` | Der er stadig en ekstra bruger. Gå tilbage til trin 5. |
| `Unexpected @ProvisioningPreCondition` | OnePlus' egen spærring. Stop her, og send mig hele fejlbeskeden. Så går vi videre med plan B. |
| `Unknown admin` | Appen er ikke installeret. Gå tilbage til trin 4. |

## 8. Læg kontiene på igen

Søg efter **Konti** i Indstillinger, og vælg *Tilføj konto* for Google og de andre.
Åbn WhatsApp og de andre apps som normalt.

Telefonen viser nu en besked om, at *enheden administreres af din organisation*.
Det er bare vores app.

## 9. Test, at det virker

Du giver telefonen ordrer med den lille hjælper `desktop\sdp.cmd` i repoet. Hver
kommando svarer med en linje som `Result: Bundle[{json={"ok":true, ...}}]`.

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

3. **Virker MitID og banken uden Play Butik?** Dette er den vigtigste test.

   ```powershell
   desktop\sdp hide com.android.vending
   ```

   Prøv nu at godkende et MitID-login (fx log ind på borger.dk på pc'en, og godkend i
   MitID-appen). Åbn også din bankapp, og log ind. Skriv ned, hvad der sker. Vis
   derefter Play Butik igen:

   ```powershell
   desktop\sdp unhide com.android.vending
   ```

4. **Lås for installation**

   ```powershell
   desktop\sdp lock
   ```

   Svaret skal indeholde `"locked":true`. Tjek nu på telefonen:
   - Søg efter **Installer ukendte apps** i Indstillinger. Det skal være spærret af
     administratoren.
   - Søg efter **Nulstil** (gendan fabriksindstillinger). Det skal også være spærret.

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

6. **Genstart telefonen**, og kør `desktop\sdp status` igen. Alt skal være som før.

**Fortæl mig bagefter:** om trin 7 virkede, hvad MitID og banken gjorde uden Play
Butik, og om noget opførte sig mærkeligt.

---

## Når testen er god: lås telefonen

Hvis MitID og banken virkede uden Play Butik:

```powershell
desktop\sdp hide com.android.vending
desktop\sdp hide com.android.chrome
desktop\sdp hide com.google.android.googlequicksearchbox
desktop\sdp lock
```

Linjerne skjuler Play Butik, Chrome og Google-appen, som også indeholder Assistent og
Lens. Har du Gemini eller Google Lens som separate apps, kan du også skjule
`com.google.android.apps.bard` og `com.google.ar.lens`. Får du svaret "Der er ingen
app med pakkenavnet", har du ikke den app.

Hvis MitID eller banken **ikke** virkede uden Play Butik, så spring den første linje
over. Play Butik er så synlig, men den kan ikke installere noget, mens telefonen er låst.

**Når du vil installere eller opdatere apps** (gør det hver eller hver anden uge, så
WebView og Google Play-tjenester bliver opdateret):

```powershell
desktop\sdp unlock
desktop\sdp unhide com.android.vending
```

Opdatér i Play Butik. Bagefter:

```powershell
desktop\sdp hide com.android.vending
desktop\sdp lock
```

## Alle kommandoer

| Kommando | Hvad den gør |
|---|---|
| `desktop\sdp status` | Viser tilstand og skjulte apps |
| `desktop\sdp list` | Viser alle apps på telefonen. Listen er lang og er mest til pc-programmet i trin 2 |
| `desktop\sdp hide PAKKE` | Skjuler en app helt |
| `desktop\sdp unhide PAKKE` | Viser en app igen |
| `desktop\sdp lock` | Låser: intet kan installeres eller opdateres |
| `desktop\sdp unlock` | Åbner for installation. Beskyttelsen forbliver slået til |
| `desktop\sdp release JA` | Fjerner det hele igen (se nedenfor) |

**Beskyttelsen**, som er slået til fra første `lock` eller `unlock`, spærrer for:

- installation af APK-filer, fx fra Filer, Messenger eller mails
- nye brugere og gæster
- sikker tilstand
- nulstilling via Indstillinger

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
almindelig app, som derefter afinstalleres.

Hvis appen ikke svarer, kan pc'en altid fjerne den direkte, fordi det er en testversion:

```powershell
adb shell dpm remove-active-admin io.github.tbmagi.smartdumbphone/.AdminReceiver
```

Vil du sætte den op igen bagefter, skal du fjerne alle konti igen (trin 6).

## Hvis noget går galt

- **`adb devices` viser `unauthorized`:** Lås telefonen op, og tryk Tillad i
  beskeden om USB-fejlfinding.
- **`adb devices` viser ingenting:** Prøv et andet kabel eller USB-stik, og vælg
  "Filoverførsel" på telefonen.
- **Svaret siger `Kun pc'en (adb over USB) må styre telefonen`:** Det burde ikke ske,
  når du bruger `desktop\sdp`. Send mig hele linjen.
- **Svaret siger `Error while accessing provider`:** Appen er ikke installeret, eller
  telefonen er ikke låst op efter en genstart.
