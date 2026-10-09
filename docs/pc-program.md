# Pc-programmet (trin 2)

Pc-programmet er et vindue, hvor du styrer telefonen med knapper i stedet for kommandoer:

- **Lås telefonen** og **Åbn for installation**
- en liste over telefonens apps, hvor du kan skjule og vise dem
- en advarsel, hvis en browser eller en app, der kan styre telefonen, ikke er skjult

Telefon-appen skal være sat op som device owner først (se
[opsaetning.md](opsaetning.md), trin 1-8). Ellers viser programmet "Ikke sat op".

## 1. Installer Python (kun første gang)

1. Gå til <https://www.python.org/downloads/>, og tryk på den gule knap
   *Download Python 3...*.
2. Kør filen. Sæt flueben i **Add python.exe to PATH** nederst, og tryk *Install Now*.

Du skal ikke installere andet. Programmet bruger kun det, der følger med Python.

## 2. Hent den nyeste kode

Åbn GitHub Desktop, og tjek, at *Current branch* er `claude/new-session-6zewu1`. Tryk
*Fetch origin* og derefter *Pull origin*, hvis knappen er der.

## 3. Start programmet

1. Sæt telefonen til pc'en med USB-kablet. USB-fejlretning skal være slået til.
2. Åbn mappen `C:\Smartdumbphone\desktop` i Stifinder, og dobbeltklik på **`start.cmd`**.

Programmet finder selv adb fra Android Studio og forbinder til telefonen. Øverst står
der, om telefonen er forbundet, og om den er låst eller åben for installation.

## 4. Sådan bruger du det

**De to store knapper**

- **Lås telefonen:** Der kan hverken installeres eller opdateres apps.
- **Åbn for installation:** Du kan installere og opdatere apps fra Play Butik. Husk at
  låse igen bagefter.

Fluebenet under knapperne bestemmer, om Play Butik skal skjules, når du låser, og vises
igen, når du åbner. Fjern det kun, hvis MitID eller din bank ikke virker uden Play Butik
(se test 3 i opsaetning.md).

**Den røde advarsel**

Står der en rød linje, fx *Browsere, der ikke er skjult: Firefox*, er der en app, som
kan bruges til at komme uden om låsen. Tryk **Skjul dem**.

**Listen over apps**

- Skriv i **Søg** for at finde en app ud fra navn eller pakkenavn.
- Vælg en eller flere apps, og tryk **Skjul valgte** eller **Vis valgte**. Hold Ctrl
  nede for at vælge flere.
- **Status** er *Synlig*, *Skjult* eller *Fjernet*. *Fjernet* betyder, at appen er
  fjernet fra telefonen på en anden måde, fx med adb.
- **Bemærkning** fortæller, om appen er en browser, Play Butik, en app, der kan styre
  telefonen, eller en app, der ikke kan skjules.
- Grå linjer kan ikke skjules, fordi telefonen skal bruge dem.
- Normalt vises kun apps med et ikon og skjulte apps. Sæt flueben i
  **Vis også Androids egne dele** for at se resten.
- **Opdater** henter listen igen fra telefonen.

## 5. Sådan bruger du det til daglig

**Første gang**

1. Find og skjul **Chrome** og **Google** (Google-appen). Har du **Gemini** eller
   **Google Lens**, så skjul dem også.
2. Står der en rød advarsel, så tryk **Skjul dem**.
3. Tryk **Lås telefonen**.

**Når du vil installere eller opdatere apps**, fx hver eller hver anden uge:

1. Tryk **Åbn for installation**.
2. Åbn Play Butik på telefonen, og vælg *Profil > Administrer apps og enhed > Opdater
   alle*. Vent, til alle apps er opdaterede.
3. Tryk **Lås telefonen**. Tjek, at der ikke står en rød advarsel.

## Nødudgang

Vælg *Avanceret > Nødudgang: fjern det hele fra telefonen* i menuen. Det viser alle
skjulte apps igen, fjerner alle spærringer og gør telefon-appen til en almindelig app.
Bagefter kan du afinstallere den med:

```powershell
adb uninstall io.github.tbmagi.smartdumbphone
```

## Hvis noget går galt

| Programmet skriver | Hvad du gør |
|---|---|
| *adb blev ikke fundet* | Android Studio skal være installeret (det følger med). Du kan også lægge mappen `platform-tools` i `C:\Smartdumbphone\desktop`. |
| *Ingen telefon fundet* | Sæt kablet i, og tjek, at USB-fejlretning er slået til. Programmet prøver selv igen hvert 5. sekund. |
| *Telefonen har ikke godkendt pc'en* | Lås telefonen op, og tryk Tillad i beskeden om USB-fejlretning. |
| *Appen på telefonen svarer ikke* | Lås telefonen op. Er appen installeret (opsaetning.md, trin 4)? |
| *Ikke sat op* | Appen er ikke device owner endnu. Følg opsaetning.md, trin 5-8. |
| *... kan ikke skjules ...* | Appen er en del af systemet. Det er en sikring, så telefonen ikke går i stykker. |
| Et vindue med *Programmet stoppede med en fejl* | Tag et skærmbillede, og send det til mig. |

Kommandoerne med `desktop\sdp` fra opsaetning.md virker stadig, hvis du får brug for dem.
