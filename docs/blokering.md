# Blokering af interne browsere og Reels (trin 5)

Mange apps har deres egen indbyggede browser. I Messenger kan man fx trykke på et link
eller en Reel og ende på Facebook eller i en uendelig strøm af videoer, selvom Chrome er
skjult. Denne funktion lukker den slags skærme automatisk.

## Sådan virker det

- Telefon-appen får en **tilgængelighedstjeneste**. Den holder øje med, hvilken skærm
  der er åben, og trykker automatisk *tilbage*, når en blokeret skærm dukker op, fx
  browseren inde i Messenger. Den læser ikke, hvad der står på skærmen.
- Tjenesten slås **til og fra fra pc'en**, aldrig på telefonen.
- **Hvis tjenesten bliver slået fra på telefonen** (fx for at omgå blokeringen), skjuler
  appen automatisk de berørte apps (Messenger), indtil tjenesten slås til igen fra pc'en.
- Reglerne for, hvad der blokeres, ligger i appen og kan opdateres fra pc'en, hvis en app
  ændrer sig. Som standard blokeres **browseren i Messenger**.

## Slå blokering til

1. Åbn pc-programmet (`desktop\start.cmd`), og forbind telefonen.
2. I feltet **Blokering af interne browsere** trykker du **Slå blokering til**.
3. Android spørger måske på telefonen, om appen må styre skærmen. Det er tjenesten.

Der står nu *Blokering er slået til* både i pc-programmet og på telefonens statusskærm.

Prøv at åbne et link i Messenger. Skærmen skal lukke sig selv igen med det samme.

> **Bemærk:** Omkring et døgn efter, at tjenesten er slået til første gang, viser Android
> måske en besked om, at appen "kan se og styre din skærm". Det er normalt og forventet.

## Reels i Messenger

Reglen rammer Messengers browser, og det dækker som regel også Facebook og Reels, der
åbnes den vej. Hvis Reels afspilles på en anden måde inde i Messenger, kan jeg lave en
præcis regel. Det kræver et billede af skærmen:

1. Slå blokering til (så tjenesten kører).
2. Åbn en Reel inde i Messenger.
3. Gå tilbage til pc-programmet, og tryk **Gem skærmen …**.
4. Programmet gemmer en fil (`desktop\data\skaerm-dump.txt`). Send den til mig, så laver
   jeg en regel, som pc'en kan sende til telefonen.

Filen indeholder kun tekniske navne på elementerne på skærmen, ikke dine beskeder.

## Slå blokering fra

Tryk **Slå blokering fra** i pc-programmet. Tjenesten slås fra, og de berørte apps er
ikke længere skjult.

## Hvis Messenger pludselig er skjult

Står der i pc-programmet, at blokering er slået til, men tjenesten ikke er aktiv, er
tjenesten blevet slået fra på telefonen. Messenger er skjult, indtil den slås til igen.
Tryk **Slå til igen** i pc-programmet.

## Begrænsninger

- En skærm kan nå at blinke kort, før den lukkes igen. Det er normalt for denne måde at
  blokere på.
- Blokeringen gælder kun de apps, der er en regel for. Andre apps med indbygget browser
  skal have deres egen regel (brug **Gem skærmen**).
- Når Messenger bliver opdateret, kan navnene ændre sig, så en regel skal opdateres. Den
  generelle browser-regel er lavet, så den holder på tværs af de fleste opdateringer.
