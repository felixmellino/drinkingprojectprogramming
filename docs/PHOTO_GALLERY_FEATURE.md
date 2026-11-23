# Feature-Beschreibung: Foto-Galerie (Check-in-Fotos)

Stand: 22. November 2026, Code auf `main` von WeGoPub. Diese Beschreibung ist so
geschrieben, dass man das Feature in einem anderen Projekt nachbauen kann. Die
Dateinamen zeigen, wo es in WeGoPub umgesetzt ist.

## 1. Worum es geht

Jeder Check-in braucht ein frisches Foto aus der Kamera. Die Galerie zeigt diese
Fotos den Mitgliedern der Lobby, in der sie gemacht wurden, wie eine Handy-
Fotogalerie: neueste zuerst, nach Spielabend gruppiert, als Kacheln im Raster.
Ein Tipp öffnet das Foto groß mit allen Details.

Grundsätze:

- **Privat als Standard.** Fremde Fotos sieht man nur, wenn der Besitzer das
  Teilen eingeschaltet hat. Fehlt die Einstellung, gilt „aus“.
- **Jede Anfrage wird frisch geprüft.** Mitgliedschaft, Einwilligung, Ablauf und
  Speicherpfad werden bei jedem Laden neu gelesen, nie aus einem Cache.
- **Foto und Punkte sind getrennt.** Ein Foto löschen ändert nie die Punkte.
- **Fotos laufen ab.** 30 Tage nach Saisonende sind sie weg.

## 2. Was der Spieler sieht

**Einstieg:** Tab „Activity“, oben ein Umschalter **Feed | Photos**
(`activity_ui.view_switch`). Photos ist die Galerie (`pages/6_Check_in_photos.py`).

**Galerie-Ansicht**

- Oben ein Umschalter **All | Mine**: alle für mich sichtbaren Fotos oder nur meine.
  Er erscheint nur, wenn es mehr als ein Foto gibt. Ein Wechsel startet wieder bei
  den neuesten Fotos.
- Fotos nach Spielabend gruppiert (Do 18:00 bis So 18:00), Überschrift pro Gruppe:
  „Game night 19–21 Nov · 7 check-ins“. Grundlage sind die Fenster der Saison
  (`photo_history_ui.game_night_bounds`); alte Einträge ohne Saison nutzen das
  Standardfenster.
- Raster: **4 Spalten** am Laptop, **3 Spalten** auf dem Handy (randlos), Kacheln
  im Format **3:4** (`assets/drink_entries.css`, `.st-key-memory_grid_*`).
- Jede Kachel (`photo_history_ui.memory_tile`):
  - das Foto, randfüllend (`object-fit: cover`), oder eine graue Fläche, wenn es fehlt;
  - unten ein dunkler Verlauf mit **Name** (im Team-Modus „Name (Team)“) und **+Punkten**;
  - oben rechts ein kleiner Punkt: **grün** = in einem Gebiet, **grau** = außerhalb.
  - Über der ganzen Kachel liegt ein unsichtbarer Knopf („View Mia's check-in“), so
    ist sie antippbar und für Screenreader beschriftet.
- **24 Fotos** zuerst, „Load more“ lädt jeweils 24 weitere, darunter „48 of 120 photos“.
- Fußzeile: „Photos stay until 30 days after their season ends. Deleting your
  photo keeps your score. Sharing: Profile → Account & security → Photo privacy.“

**Leere Zustände**

- Keine Fotos: Karte „No photos yet. Every check-in adds one here.“ mit Check-in-Knopf.
- „Mine“ ohne eigene Fotos: „None of yours yet.“

**Detail-Ansicht (ein Foto geöffnet)**

- „Back to photos“ oben.
- Das Foto fast bildschirmfüllend (`photo_history_ui.full_photo`), unten auf
  dunklem Verlauf **Name** und **Ort** (Gebiet, „Outside game territories“ oder
  „No territory assigned“). Fehlt das Bild: „Photo unavailable“.
- Darunter: Zeitpunkt („Photo received …“ oder „Check-in submitted …“).
- **Punkte & Details**: Getränk und Größe, Saison- und Gebietspunkte,
  Besitzer-Einkommen (an wen), Boost-Hinweise (Time Duel ×1.25, Focus), Hinweis
  bei Chug Duel. Ausklappbar: exakte Zeitstempel und Korrektur-Historie.
- **Korrigieren** (nur der Besitzer, nur 2 Minuten nach dem Absenden, nicht bei
  Duellen): Getränk/Größe neu wählen, neue Basispunkte als Vorschau, „Save
  correction“. Danach werden Besitz und Einkommen neu berechnet.
- **Foto löschen** (nur der Besitzer): unter „Manage your photo“, mit Häkchen
  „Permanently delete this photo“ als Bestätigung. Meldung danach: „Photo
  deleted. Your score is unchanged.“
- Wer nicht Besitzer ist, liest einen kurzen Hinweis statt der Knöpfe.

**Einstellung zum Teilen:** Profil → Account & security → **Photo privacy**, ein
Schalter für alle Fotos des Kontos, in allen Lobbys, rückwirkend
(`profile_ui.py`).

## 3. Datenmodell

| Wo | Was |
| --- | --- |
| Tabelle `drink_entries` | Der Check-in. `photo_ref` = `"{lobby_id}/{entry_id}.jpg"`, solange das Foto existiert; danach `"deleted"` oder `"expired"`. Dazu `photo_captured_at`, `submitted_at`, `location_check_result` (`matched`/`outside`), `territory_id`, `team_id`, Punkte. |
| Tabelle `player_photo_preferences` | `player_id`, `share_checkin_photos` (bool). Fehlt die Zeile = nicht teilen. |
| Storage-Bucket `check-in-photos` | **Privat.** Ein Objekt pro Check-in unter `{lobby_id}/{entry_id}.jpg`. Keine öffentlichen URLs, keine signierten Links. |
| Konstanten (`core/constants.py`) | `PHOTO_RETENTION_DAYS = 30`, `UNLINKED_PHOTO_GRACE_HOURS = 24` |

Alle Tabellen und der Bucket sind nur mit dem Server-Schlüssel zugänglich
(Migration `013_checkin_photo_privacy.sql`). Der Browser bekommt nie direkten
Zugriff, er sieht nur Bilder, die der Server nach der Prüfung ins HTML einbettet.

## 4. Hochladen (beim Check-in)

1. **Nur Kamera**, kein Upload aus der Mediathek (`camera_capture.py`,
   `components/drink_camera/`). Die Kamera schneidet auf das sichtbare Format zu,
   max. 1600 px.
2. **Prüfen und säubern** (`core/checkin_photo.prepare_checkin_photo`):
   - höchstens **10 MB** und **20 Megapixel**, geprüft vor dem Dekodieren;
   - nur JPEG; Schutz gegen „Decompression Bombs“;
   - Ausrichtung übernehmen, dann **neu als JPEG (Qualität 90) ohne Metadaten**
     speichern: kein EXIF, keine GPS-Daten im gespeicherten Bild.
3. **Erst das Foto, dann der Eintrag** (`db.save_drink_entry_photo`): Foto unter
   dem festen Pfad hochladen, danach den Check-in mit derselben ID speichern. Ein
   erneuter Versuch nach verlorener Antwort nutzt dieselbe ID und vergibt keine
   doppelten Punkte. Schlägt das Speichern fehl, bleibt höchstens ein
   unverknüpftes Foto, das die Aufräum-Routine nach 24 h entfernt.

## 5. Wer welches Foto sehen darf

Die Regel steht an einer Stelle: `core/photo_privacy.can_view_photo`.

```text
Betrachter ist kein aktuelles Mitglied der Lobby      -> nein
Betrachter ist der Besitzer                            -> ja
Einzel-Lobby:  Besitzer hat Teilen an                   -> ja, sonst nein
Team-Lobby:    Betrachter im selben Team wie das Foto   -> ja (teamintern immer)
               sonst: Team hat Mitglieder UND Besitzer
               UND jedes aktuelle Teammitglied teilt     -> ja, sonst nein
```

Dazu kommen:

- **Ablauf:** Ab `season_ends_at + 30 Tage` wird kein Bild mehr ausgeliefert,
  auch vor der Aufräum-Routine (`core/checkin_photo.photo_expires_at`).
- **Pfadprüfung:** Ausgeliefert wird nur, wenn `photo_ref` genau dem erwarteten
  Pfad entspricht. Ein gelöschtes Foto (`"deleted"`) kommt nie zurück.
- **Fehlerverhalten:** Kann die Einwilligung nicht gelesen werden, gibt es kein
  Bild. Es wird nie auf „sichtbar“ zurückgefallen.
- Fehlt der Zugriff bei einem einzelnen Bild, gilt das als `PermissionError`, und
  die Seite sagt „Photo access changed. Refresh …“.

Diese Prüfung läuft in drei Funktionen (`data/db.py`), jedes Mal frisch:
`list_checkin_photos` (Liste), `download_checkin_photos` (Galerie-Paket),
`download_checkin_photo` (ein Foto groß). Ausschalten des Teilens wirkt also ab
der nächsten Anfrage. Schon angezeigte, heruntergeladene oder abfotografierte
Bilder lassen sich nicht zurückholen; das steht so auch in der Regel R-PH01.

## 6. Laden und Geschwindigkeit

**Liste** (`list_checkin_photos`): **eine** Abfrage auf `drink_entries` mit
Joins auf Gebietsname, Saison und Mitgliedschaft samt Benutzername, gefiltert
auf die Lobby, neueste zuerst. Dazu frisch: Mitglieder der Lobby und die
Teilen-Einstellungen aller beteiligten Spieler (eine Abfrage). Abgelaufene und
nicht erlaubte Einträge werden ausgefiltert, bevor die Seite sie sieht.

**Bilder in Paketen** (`download_checkin_photos`):

- höchstens **12 Fotos pro Paket** (`MAX_PHOTO_BATCH`). Jedes Paket bekommt seinen
  eigenen frischen Rechte-Schnappschuss, und alle Rechte werden geprüft, **bevor**
  irgendein Bild geladen wird.
- Die Downloads eines Pakets laufen **parallel**.
- Für die Kacheln wird ein **Vorschaubild** erzeugt (max. 360 × 480, JPEG 80,
  `core/checkin_photo.photo_thumbnail`). Die Detailansicht lädt immer das Original.
- **Kurzer Vorschau-Cache pro Browser-Sitzung:** höchstens 48 Vorschaubilder für
  45 Sekunden, nur für dieselbe Lobby. Wiederverwendet wird ein Bild erst,
  nachdem Rechte, Ablauf und Pfad im aktuellen Paket erneut geprüft wurden. Nach
  dem Löschen eines Fotos wird der Cache geleert.
- Die Prüfung, ob der Bucket privat ist, läuft einmal alle 10 Minuten pro
  Server-Prozess statt vor jedem Bild. Eine Ablehnung wird nie gespeichert.
- Schlägt ein Paket fehl, laden die anderen trotzdem. Die Seite zeigt „Some
  photos could not be loaded. Their details are still available.“

Gemessen (Audit 20. November, 12 Vorschaubilder): kalt 644 ms und 1,97 MB aus
dem Speicher, aus dem Cache 278 ms und 5,4 kB.

## 7. Löschen und Aufbewahrung

- **Löschen durch den Besitzer** (`delete_checkin_photo`): Besitz prüfen, Objekt
  aus dem Bucket entfernen, dann `photo_ref` auf `"deleted"` setzen, aber nur,
  wenn es noch der alte Pfad ist. Doppelt löschen ist harmlos. Punkte,
  Besitzverhältnisse und Einkommen bleiben unverändert.
- **Automatisches Aufräumen** (`data/cleanup_checkin_photos.py`): Ohne `--apply`
  zählt das Skript nur, mit `--apply` löscht es abgelaufene Fotos (30 Tage nach
  Saisonende, `photo_ref` danach `"expired"`) und unverknüpfte Uploads, die älter
  als 24 Stunden sind. Es läuft täglich um 04:17 UTC als GitHub Action
  (`.github/workflows/photo-cleanup.yml`) und lässt Punkte unverändert.

## 8. Fehlermeldungen (alle ohne technische Details)

| Situation | Meldung |
| --- | --- |
| Keine Mitgliedschaft in der Lobby | „Choose a lobby you belong to to view its photos.“ |
| Datenbank/Speicher nicht erreichbar | „We couldn't load the photo. Try again.“ |
| Rechte haben sich geändert | „Photo access changed. Refresh to load the current photo history.“ |
| Einzelne Bilder fehlen | „Some photos could not be loaded. Their details are still available.“ |
| Löschen ohne Häkchen | „Deletion has not been confirmed. Tick Permanently delete this photo …“ |
| Löschen unsicher | „We couldn't confirm deletion. Refresh Photos to check …“ |
| Fremdes Foto löschen | „Only the photo's owner can delete it. Use the Mine filter …“ |

## 9. Tests in WeGoPub

- `tests/test_photo_privacy.py`: die Sichtbarkeitsregel (Einzel, Team, fehlende
  Einwilligung, neues Teammitglied ohne Teilen, leeres Team, Ex-Mitglied).
- `tests/test_photo_lifecycle.py`: Löschen, Ablauf, Aufräumen, verlorene Antworten,
  Pakete mit Rechte-Schnappschuss, Vorschau-Cache.
- `tests/test_checkin_photo.py`: Größen- und Pixelgrenzen, Metadaten entfernt,
  Ausrichtung, defekte Bilder, privater Bucket.
- `tests/test_scoring_ui.py`: Galerie-Seite mit echten Streamlit-Widgets
  (Gruppierung, All/Mine, Detail, Korrektur).

## 10. In ein anderes Projekt übernehmen

**Allgemein übertragbar (unabhängig von Streamlit):**

1. Privater Speicher-Bucket, Pfad `{gruppe}/{eintrag_id}.jpg`, Eintrag speichert
   den Pfad oder `"deleted"`/`"expired"`.
2. Tabelle mit der Teilen-Einstellung pro Nutzer, Standard „aus“.
3. Eine einzige Regel-Funktion für „darf X dieses Foto sehen?“ und überall nur
   diese benutzen.
4. Rechte bei jeder Anfrage frisch lesen, nie aus einem Cache. Bei unklaren Rechten
   kein Bild ausliefern.
5. Bilder beim Hochladen säubern: Größen- und Pixelgrenze, neu kodieren ohne
   Metadaten.
6. Erst das Bild speichern, dann den Eintrag, mit einer festen ID (idempotent).
7. Pakete von höchstens 12 Bildern, Rechte vor dem Download prüfen, parallel laden,
   kleine Vorschaubilder für das Raster.
8. Ablaufdatum serverseitig prüfen und ein tägliches Aufräum-Skript mit
   Probelauf-Modus.
9. Löschen entfernt nur das Bild, nie die Daten dahinter.

**Streamlit-spezifisch (in WeGoPub so gelöst):**

- Bilder als `data:image/jpeg;base64,…` per `st.html` einbetten, nie über
  öffentliche URLs.
- Raster per CSS-Grid auf einem Container mit `key` (`st-key-memory_grid_*`),
  Kacheln mit einem unsichtbaren, randfüllenden `st.button` antippbar machen.
- Zustand in `st.session_state`: geöffnetes Foto (`history_detail_id`), Filter,
  Anzahl angezeigter Fotos, Vorschau-Cache (`_gallery_thumbnails`).
- Mehr laden mit einem `on_click`-Callback statt `st.rerun`.

**Anpassen:** Gruppierung (bei uns Spielabend Do–So), Spaltenzahl, Paketgröße,
Aufbewahrungsdauer und ob Teams eine eigene Sichtbarkeitsregel brauchen.
