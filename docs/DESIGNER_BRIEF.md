# WeGoPub – Briefing für das Design

## Worum es geht
WeGoPub ist ein Trinkspiel als Handy-App für Studierende in Lissabon (Uniprojekt, Nova SBE).
Freunde treten in einer **Lobby** eine Saison lang (ca. ein Monat) gegeneinander an. An Spielabenden
(Do–So) loggt man jedes Getränk mit **Foto**, der Standort ordnet es einem **Gebiet** auf der Karte zu.
Wer in einem Gebiet die meisten Punkte hat, besitzt es. Wer am Ende der Saison die meisten Punkte hat, gewinnt.

Live: https://wegopubnow.streamlit.app/ · Präsentiert wird im Kurs über ein gespiegeltes iPhone.

## Für wen, welche Stimmung
- Studierende, 20–26, abends unterwegs in Bairro Alto, Cais do Sodré, Nova-Campus.
- Spielerisch und sozial, aber **clean und ruhig**: wenig Text, große Tipp-Flächen, keine Slogans.
- Lissabon-Bezug: gelbe Tram, Azulejos, Nachtstimmung.

## Die App (mobile first, iPhone-Format)
Untere Leiste mit 5 Tabs, rundes **Profil**-Icon oben rechts auf jeder Seite.

| Tab | Inhalt |
|---|---|
| **Map** | Vollbild-Karte mit 48 Gebieten (blau = meins, rot = Gegner, grau = frei). Oben eine Leiste mit Lobby und Stand, darunter die Pillen *Lisbon* / *Nova* und ein *Location*-Schalter. Unten eine schmale Karte „Du bist in …“ mit Tauziehen-Balken. |
| **Ranks** | Rangliste der Saison (Podium für Platz 1–3, darunter eine Liste). |
| **+ Check in** | Kamera zuerst, dann auf **einem** Bildschirm: großes Foto, Getränk und Größe als kleine Pillen, Punkte, Standort, *Submit*. Danach Ergebnis und *Go to map*. |
| **Games** | Minispiele als Kachel-Raster: Chug Duel, Reaction Duel, Quiz Duel, Time Duel. |
| **Photos** | Galerie wie die Erinnerungen einer Handy-App: Raster nach Spielabend, *All / Mine*, Foto antippen öffnet es fast im Vollbild. |

Weitere Seiten: Profil (Lobbies, Freunde, Statistiken, Konto, Location-Schalter), Login mit **Startbildschirm**.

## Design-System (bestehend)
- **Schriften:** *Anton* (Überschriften, groß und schmal), *Barlow* (Text und Knöpfe). Der Schriftzug „WeGoPub“ steht in Barlow 800, „Pub“ in Rot.
- **Farben:** Navy `#142B3D` (Text), Hintergrund `#F8FAFC`, Himmelblau `#2C99D6` (Akzent, „meins“), Rot `#EB2F33` (Marke, „Gegner“), Grau `#8A97A6` (frei).
- **Formen:** runde Ecken (Pillen, 16–24 px Radius), weiße halbtransparente Glasflächen mit Blur über der Karte, weiche Schatten.
- **Icons:** Phosphor (Linien-Icons), gefüllt für den aktiven Tab.
- Alle Werte liegen in `assets/theme.css`, die Regeln in `docs/DESIGN_GUIDELINES.md`.

## Rahmenbedingungen
- Gebaut mit **Streamlit** (Python). Gestaltet wird über CSS und HTML, eigene Animationen gehen nur in CSS.
- Muss auf iPhones von 375 bis 430 px Breite funktionieren, Check-in und Karte ohne Scrollen.
- Fotos und Schriften brauchen eine **freie Lizenz** oder eigene Rechte (Repo und App sind öffentlich).

## Gerade in Arbeit / offen für Ideen
- **Startbildschirm (umgesetzt):** heller Grund, App-Icon „WP“ in Himmelblau, Schriftzug „WeGo“ navy + „Pub“ blau, unten *Create account* (blau) und *Log in* (Text). Kurzer Einstieg (Icon ploppt, Schriftzug gleitet hoch), sonst ruhig. Erscheint bei **jedem Öffnen der App**: Wer noch eingeloggt ist, sieht Icon und Schriftzug mit „Tap to continue“, ein Tipp irgendwo führt weiter.
- Profil- und Lobby-Seite optisch an Karte, Ranks und Photos angleichen.
- Kleine Ladeanimationen und Leerzustände („noch keine Fotos“ usw.).
