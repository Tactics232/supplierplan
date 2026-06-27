# Einstellungen – was bedeutet was?

Erklärung aller Felder im Einstellungen-Fenster der Supplierplan-App, gruppiert
nach den Reitern. Pflichtfelder sind nur die unter **WebUntis** – der Rest hat
sinnvolle Standardwerte.

---

## Reiter „WebUntis" (Pflicht)

| Feld | Bedeutung |
|---|---|
| **WebUntis-URL** | Adresse deiner WebUntis-Instanz, z. B. `https://deineschule.webuntis.com`. |
| **Schul-ID** | Die `school`-Kennung (Form `sXXXXXX`). Steht in der WebUntis-Login-URL hinter `?school=`. |
| **Benutzer** | Service-/Anzeige-Account in WebUntis (Leserechte auf Vertretungen genügen). |
| **Passwort** | Passwort dieses Accounts. Wird maskiert angezeigt und nur lokal in `config.env` gespeichert. |
| **Abteilungs-ID** | Filtert Vertretungen auf eine Abteilung (`0` = alle). Nur bei mehreren Abteilungen nötig. |
| **Pseudo-Lehrer (Komma)** | Schul-eigene Platzhalter-Lehrer (z. B. `Z Entfall`), die wie „kein Lehrer" behandelt werden. |

Mit **„Verbindung testen"** prüfst du Login-Daten, ohne zu speichern.

---

## Reiter „Schule"

| Feld | Bedeutung |
|---|---|
| **Schulname** | Name im Kopf/Fuß der Anzeige. |
| **Schultyp** | Untertitel-Teil (z. B. „Mittelschule"). |
| **Ort** | Ortsangabe in Kopf/Fuß. |
| **Plan-Titel** | Titel der Anzeige und des Browser-Tabs (z. B. „Supplierplan", „Vertretungsplan"). |
| **Logo-Datei** | Dateiname des Logos. Über **„…"** ein Bild auswählen – es wird in den Anzeige-Ordner kopiert. |
| **Morgen ab (HH:MM)** | Ab dieser Uhrzeit wird zusätzlich der nächste Schultag gezeigt (sonst erst wenn heute leer ist). |
| **Zeitzone** | IANA-Zone für „heute/morgen" und die Uhr (Standard `Europe/Vienna`). |

---

## Reiter „Züge"

Optionales Zug-Widget im Kopf. Leer lassen oder **Deaktiviert = true** blendet es aus.

| Feld | Bedeutung |
|---|---|
| **Station** | Exakter Haltestellenname. Über **„Suchen…"** live in der ÖBB-Datenbank nachschlagen und auswählen. |
| **Richtung (Komma)** | Zielnamen, die als „stadteinwärts/­auswärts" gelten (Substring-Treffer), zur Sortierung der Richtungen. |
| **Züge je Richtung** | Wie viele nächste Abfahrten pro Richtung angezeigt werden. |
| **Produkte (z. B. S,REX)** | Nur diese Zuggattungen zeigen (Präfix-Treffer). Leer = alle (inkl. Bus). |
| **Deaktiviert** | `true` blendet das ganze Zug-Widget aus. |

---

## Reiter „Anzeige"

| Feld | Bedeutung |
|---|---|
| **Theme** | `dark` oder `light` Farbschema. |
| **Uhr zeigen** | Datum + Uhrzeit im Kopf ein-/ausblenden. |
| **Logo zeigen** | Logo im Kopf ein-/ausblenden. |
| **Compact-Schwelle px** | Ab welcher Spaltenbreite die kompakte Darstellung (runde Badges, kürzere Texte) greift. |
| **Text-Badges** | Bemerkungs-Codes, die als Badge statt als Text erscheinen (Standard `b,ub,MA`). |
| **Max. Spalten** | Obergrenze der Spaltenzahl im Layout (1–4). Niedriger = breitere Spalten. |
| **Entfall-Platzierung** | `section` = alle Entfälle gesammelt am Tagesende; `inline` = beim jeweiligen Lehrer. |
| **PWA-Orientierung** | Bildschirm-Sperre der installierten Handy-/Tablet-App. `any` = frei drehbar. |

---

## Reiter „Überlauf"

Greift gestuft, wenn der Plan zu voll für den Bildschirm wird: **Skalieren → Reduzieren → Blättern**.

| Feld | Bedeutung |
|---|---|
| **Skalieren** | Gesamtes Board verkleinern, bevor etwas ausgeblendet wird. |
| **Min-Faktor (0.3–1.0)** | Untergrenze der Verkleinerung (z. B. `0.65`). |
| **Reduzieren** | Bei Platzmangel Text-Spalte aus, dann Entfall-Sektion kompakt. |
| **Blättern** | Reicht der Platz immer noch nicht: seitenweise durchblättern. |
| **Sekunden je Seite** | Anzeigedauer pro Blätter-Seite. |

---

## Reiter „Cloudflare" (optional)

Nur nötig, wenn die Anzeige zusätzlich extern (über Cloudflare) erreichbar ist und
der Cache nach jedem Update geleert werden soll. Leer lassen = nichts wird gepurged.

| Feld | Bedeutung |
|---|---|
| **Zone-ID** | Cloudflare-Zone der Domain. |
| **API-Token** | Token mit Recht „Zone → Cache Purge". |
| **Host** | Nur diesen Hostnamen purgen (leer = ganze Zone). |

---

## Reiter „Server"

| Feld | Bedeutung |
|---|---|
| **Port** | Port des lokalen Webservers (Standard `8080`). Anzeige unter `http://<PC-IP>:<Port>`. |
| **Untis-Intervall (s)** | Wie oft der Plan neu geholt wird (Standard `300` = 5 min). |
| **Zug-Intervall (s)** | Wie oft die Zugdaten geholt werden (Standard `60`). |

---

Die Abwesenheits-Leisten (abwesende Lehrer/Klassen) werden zusätzlich automatisch
um **07:35 / 11:00 / 16:00** aktualisiert und lassen sich jederzeit über
**„Abwesenheiten aktualisieren"** manuell anstoßen.
