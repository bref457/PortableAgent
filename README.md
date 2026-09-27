# PortableAgent

PortableAgent ist der neue, modulare Nachfolger des bestehenden lokalen
Tabellenprojekts PortableLLM. Die Anwendung soll sensible Dateien vollstaendig
lokal analysieren: ohne Cloud-LLM, ohne Telemetrie und mit nachvollziehbaren
Quellenbelegen.

`D:\PortableLLM` ist ausschliesslich Referenzprojekt. PortableAgent darf zur
Laufzeit nicht davon abhaengen und nimmt dort keine Aenderungen vor.

## Aktueller Stand

Vorhanden sind die Architektur-Baseline, typisierte Plan-/Belegmodelle, ein
lokaler llama.cpp-Client, eine zentrale Planvalidierung, ein semantischer
Katalog sowie die deterministische Python-Tabellenengine fuer v0.1 mit
synthetischer In-Memory-Quelle und Zeilenbelegen. Modell-JSON wird strikt und
ohne stille
Typumwandlung in Analyseplaene konvertiert. Ein schema-only `PlanGenerator`
verbindet natuerliche Fragen mit diesem Ablauf, ohne Tabellenzeilen oder
Zellwerte an den Planner zu geben. Der semantische Katalog wird relativ zum
Projekt geladen, strikt validiert und nur auf vorhandene Spalten angewendet.
Ein `TableAgent` bindet Quelle, Planner und Katalog fuer wiederholte lokale
Fragen. Semantische Aggregationsregeln und notwendige Rueckfragen werden lokal
erzwungen und nicht dem Modell ueberlassen. CSV-Dateien koennen ueber einen
read-only Standardbibliotheks-Adapter und eine strikte Endungs-Allowlist
geladen werden. XLSX/XLSM werden mit `openpyxl` read-only, ohne Formel- oder
Makroausfuehrung verarbeitet. Ein minimaler `TableWorkflow` verbindet eine
einzelne explizite CSV-/XLSX-/XLSM-Abfrage mit Router, `TableAgent` und
semantischem Katalog, ohne die Tabellenquelle in einer Session oder Datenbank
zu halten. Ein strikter `TableJsonController` validiert die transportneutrale
Einzelanfrage und serialisiert Ergebnisse, Rueckfragen und Quellenbelege in
feste Strukturen. Der bestehende Loopback-Server stellt diese Grenze unter
`POST /api/table` bereit und verwendet dafuer denselben lokalen llama.cpp-
Client mit einem schema-only Planprompt. Die lokale Oberfläche besitzt einen
getrennten Tabellenmodus fuer Einzelabfragen, Resultate, Rueckfragen und
Zeilenbelege. CSV, XLSX und XLSM werden ueber einen lokalen Dateidialog
ausgewaehlt. Bei Excel-Dateien erscheinen die vorhandenen Reiter in einer
Auswahlliste; fuer die Berechnung wird bewusst genau ein Reiter verwendet.
Eindeutige Fragen wie `Wann war der letzte Einsatz im Jahr 2026?` werden bei
einer erkannten Datumsspalte deterministisch als Jahresbereich mit groesstem
Datum ausgefuehrt. Ist eine eindeutige Aktionsspalte vorhanden, erscheint der
zugehoerige Aktionsname automatisch im selben Ergebnis. Datumswerte zeigt die
deutsche Oberflaeche als `TT.MM.JJJJ`. Dadurch haengt diese haeufige Frage
nicht von einem zufaellig formulierten Modellplan ab und muss nicht in zwei
separate Fragen aufgeteilt werden.
Angebotene Rueckfrageoptionen koennen einmalig lokal
ausgewaehlt werden; der bereits validierte Plan wird dabei ohne weiteren
Modellaufruf ausgefuehrt und anschliessend aus dem Arbeitsspeicher entfernt.
Fuer den Dokumentmodus existiert bereits
eine getrennte Chunk- und Fundstellenabstraktion sowie ein read-only
UTF-8-TXT-Adapter, ein minimaler read-only DOCX-Adapter mit Absatzbelegen und
ein begrenzter lokaler PDF-Adapter mit Seitenbelegen.
Relevante Dokumentchunks werden lokal und deterministisch ohne Embeddings oder
externe Dienste gesucht. Ein
`DocumentAgent` gibt nur diese Treffer an eine austauschbare lokale
Antwortkomponente weiter und bindet Antworten an deren Fundstellen. Der lokale
llama.cpp-Adapter akzeptiert dafuer nur ein minimales JSON-Antwortformat.
Ausdruecklich bestaetigte Wissensnotizen koennen getrennt davon in einem
minimalen lokalen SQLite-Repository gespeichert werden; Dokumentinhalte und
Chatverlaeufe gehoeren nicht in dieses Schema. Ein strikter transportneutraler
JSON-Controller erlaubt nur Auflisten, bestaetigtes Anlegen und bestaetigtes
Loeschen solcher Notizen. Derselbe Controller ist lokal unter
`POST /api/memory` eingebunden. Der getrennte Memory-Modus der Weboberflaeche
erlaubt Speichern erst nach sichtbarer Bestaetigung und verlangt fuer jede
Loeschung eine eigene Rueckfrage. Eine automatische Uebernahme aus Dokumenten
oder Chatverlaeufen existiert nicht.
Geladene Dokumentquellen
koennen in eindeutig identifizierten `DocumentSession`-Objekten rein
fluechtig im Arbeitsspeicher gehalten und einzeln oder gemeinsam explizit
freigegeben werden. `SessionDocumentAgent` bindet lokale Dokumentfragen an
genau eine aktive Session; unbekannte oder bereits freigegebene IDs werden
vor einem Antwort- beziehungsweise Modellaufruf abgewiesen. Der zentrale
`open_document_session`-Use-Case oeffnet explizit angegebene TXT-, DOCX- und
PDF-Dateien ueber die Format-Allowlist und registriert sie erst nach
erfolgreicher read-only Validierung. `DocumentWorkflow` fasst Import,
sitzungsgebundene Frage und explizite Freigabe als gemeinsame lokale
Anwendungsgrenze fuer die spaetere Weboberflaeche zusammen. Ein strikter,
transportneutraler JSON-Controller validiert die dafuer vorgesehenen
Operationen und serialisiert Antworten mit festen Quellenbeleg-Strukturen;
ein kleiner Standardbibliotheks-Adapter stellt diese Grenze bei explizitem
Start ausschliesslich unter `127.0.0.1` bereit. Beim Import wird kein Server
automatisch gestartet und Request-Logging bleibt deaktiviert. Die lokale
Anwendungskomposition verbindet diese Bausteine mit dem llama.cpp-Adapter und
gibt beim Shutdown alle Sessions sowie den Socket garantiert frei.

Im Dokumentmodus ersetzt ein einzelner Button den manuellen Dateipfad. `Datei
auswaehlen und oeffnen` oeffnet den lokalen Dateidialog und liest ein
ausgewaehltes TXT-, DOCX- oder PDF-Dokument direkt ein; ein zweiter Klick ist
nicht erforderlich. Der Browser uebergibt die Datei nur an den lokalen
PortableAgent-Dienst auf `127.0.0.1`. Eine kurzlebige lokale Arbeitskopie wird
nach dem Aufbau der In-Memory-Sitzung sofort entfernt. Dateiname, Format und
Groesse werden vor der Verarbeitung geprueft.

Der Kopfbereich unterscheidet den Zustand der PortableAgent-Oberflaeche vom
lokalen Modell. Die llama.cpp-Bereitschaft wird nur ueber einen kurzen
Loopback-Health-Request ohne Nutzdaten, Proxy oder Redirect geprueft. Ein
nicht gestartetes Modell beeintraechtigt die Erreichbarkeit der Oberfläche
nicht.

Kann das lokale Modell noch nicht erreicht werden, antwortet die lokale API
mit einem klaren 503-Servicefehler. Technisch ungueltige Modellantworten werden
getrennt als 502 gemeldet. Beide Antworten bleiben absichtlich frei von
internen Endpunkten, lokalen Pfaden und Ausnahmedetails.

Eine lokale Asset-Erkennung kann rein lesend feststellen, ob an den
fest definierten relativen Pfaden unter `runtime/llama.cpp/` eine Serverdatei
und direkt unter `models/` GGUF-Modelle vorhanden sind. Dabei werden nur
Dateiname und Groesse erfasst. Die freigegebene CPU-Runtime und das
Qwen3-4B-Instruct-2507-Q4_K_M-Modell sind dort inzwischen lokal vorhanden,
gehasht und lizenziert dokumentiert. Sie bleiben per `.gitignore` ausserhalb
des spaeteren GitHub-Repositories.

Der Kopfbereich der Weboberflaeche zeigt getrennt, ob diese portablen KI-
Dateien vorhanden sind und ob bereits ein lokales Modell erreichbar ist. Der
Browser erhaelt dabei nur Verfuegbarkeit und Anzahl, keine Dateinamen oder
absoluten Pfade.

Aus einer ausdruecklich ausgewaehlten, zuvor erkannten Runtime und einem
GGUF-Modell kann bereits ein strikt validierter relativer llama.cpp-Startplan
erzeugt werden. Dieser Plan ist nur ein unveraenderlicher Argumentvektor und
startet weder eine Shell noch einen Prozess.

Ein separater Prozessmanager kann einen solchen Plan ausdruecklich
mit `shell=False` starten und ausschliesslich den eigenen Kindprozess wieder
beenden. Die Anwendung kann einen solchen bereits gestarteten Kindprozess beim
Shutdown garantiert mit aufraeumen. Die CLI-Auswahl ist vorhanden und wurde
mit einem synthetischen Tabellen-End-to-End-Test gegen das echte lokale Modell
verifiziert. Der normale Batchstart verwendet die automatische Auswahl fuer
genau ein erkanntes Runtime-/Modellpaar. Eine spaetere manuelle Modellauswahl
in der Weboberflaeche ist noch nicht vorhanden.

## Lokaler Start

Unter Windows ist die einfachste Variante ein Doppelklick auf `start.bat` im
Projektstamm. Die Batchdatei verwendet ihren eigenen Speicherort, sodass der
Laufwerksbuchstabe der externen SSD beziehungsweise des USB-Datentraegers
wechseln darf. Sie oeffnet nach dem Start die lokale Seite im Standardbrowser.
Wenn genau eine erlaubte llama.cpp-Runtime und genau ein GGUF-Modell erkannt
werden, startet sie beide automatisch zusammen mit PortableAgent. Bei
fehlenden oder mehreren Kandidaten bricht sie mit einer klaren Meldung ab,
statt willkuerlich ein Asset auszuwaehlen.
Die Rueckfrage `J/N` erscheint nur, wenn bereits eine PortableAgent-Instanz
auf dem lokalen Port laeuft. Ist der Port frei, startet die Anwendung direkt.

Der Button `PortableAgent beenden` in der Kopfzeile beendet nach einer
Bestaetigung den lokalen Webserver, temporaere Sitzungen und einen verwalteten
llama.cpp-Modellprozess. Wurde `start.bat` per Doppelklick gestartet, schliesst
sich danach auch das CMD-Fenster automatisch. Der Browser-Tab zeigt nur noch
die Abschlussmeldung und kann geschlossen werden.

Die freigegebene portable Python-Laufzeit liegt unter
`runtime/python/python.exe` und enthaelt die lokal benoetigten Pakete. Die
Batchdatei verwendet sie bevorzugt; ein installiertes Python ist fuer den
normalen Start nicht mehr erforderlich. Gefundene alternative Python-
Installationen mit zu alter Version oder fehlenden Paketen werden weiterhin
automatisch uebersprungen.
Eine reine Pruefung ohne Start ist mit `start.bat --check` moeglich.

## Erster Test mit synthetischen Beispieldaten

Nach dem lokalen Start koennen die erfundenen Dateien unter
`examples/synthetic/` direkt ueber den Dateidialog der Oberflaeche ausgewaehlt
werden. `einsaetze.csv` demonstriert den Tabellenmodus und `projektinfo.txt`
den Dokumentmodus. Eigene Dateien werden genauso ausgewaehlt; sie muessen
nicht in das Projekt kopiert werden und werden nicht automatisch dauerhaft
gespeichert.

Runtime, Modell und Nutzdaten werden nicht aus GitHub geladen. Die erwarteten
lokalen Ordner, verifizierten Quellen und Pruefschritte beschreibt
`THIRD_PARTY_ASSETS.md`.

Der aktuelle v0.1-Abgleich bestaetigt die lokalen Analyse-, Beleg-, Memory-
und Datenschutzpfade einschliesslich der portablen Python-Laufzeit. Offen ist
noch der physische Smoke-Test unter einem anderen Laufwerksbuchstaben oder auf
einem zweiten Windows-Rechner. Die priorisierte Restpunktliste steht in
`PROJECT_STATUS.md`.

Nach lokaler Paketinstallation kann die API alternativ explizit gestartet
werden:

```powershell
portable-agent
```

Alternativ funktioniert `python -m portable_agent`. Standardmaessig wird nur
`http://127.0.0.1:8765` gebunden und ein bereits laufender llama.cpp-Endpunkt
unter `127.0.0.1:8080` verwendet. Verfuegbare lokale Optionen zeigt
`portable-agent --help`. Der Befehl startet weder llama.cpp noch einen Browser
automatisch; `Ctrl+C` beendet Server, Sessions und Socket kontrolliert.

Wenn eine portable llama.cpp-Runtime und ein GGUF-Modell bereits in den
vorgesehenen Projektordnern liegen, koennen beide ausdruecklich gemeinsam
gestartet werden:

```powershell
python -m portable_agent --local-runtime runtime/llama.cpp/llama-server.exe --local-model models/DEIN-MODELL.gguf
```

Mit den aktuell bereitgestellten Assets lautet der direkte Entwicklungsstart:

```powershell
python -m portable_agent --local-runtime runtime/llama.cpp/llama-server.exe --local-model models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf
```

Die Pfade muessen zuvor von der lokalen Allowlist-Erkennung gefunden werden.
Der Modellprozess verwendet `127.0.0.1:8080` und wird beim Ende von
PortableAgent mit beendet. Ohne diese beiden Optionen startet weiterhin kein
Modellprozess.

Die aktuell erkannten relativen Pfade lassen sich ohne Server- oder
Prozessstart anzeigen:

```powershell
.\start.bat --list-local-assets
```

Die Batchdatei waehlt dabei dieselbe geeignete lokale Python-Laufzeit wie beim
normalen Start und setzt den relativen Paketpfad automatisch. Der direkte
Aufruf mit `python -m portable_agent` setzt dagegen eine installierte
PortableAgent-Entwicklungsumgebung voraus.

Die lokale Oberfläche ist danach unter
`http://127.0.0.1:8765/` erreichbar. Sie verwendet ausschliesslich
mitgelieferte Paketressourcen und kommuniziert nur mit dem gleichen lokalen
Server. Dokument- und Tabelleninhalte werden weder im Browser gespeichert
noch an externe Ressourcen gesendet. Zwischen Dokument-, Tabellen- und
Memory-Modus kann direkt in der Seite gewechselt werden.

## Struktur

```text
config/                 semantische und technische Konfiguration
src/portable_agent/
  agent/                Agent Core und lokale Workflows
  analysis/             deterministische Python-Tabellenengine
  citations/            spaeterer Citation Store
  domain/               gemeinsame Typen
  llm/                  lokale Modelladapter
  memory/               spaetere SQLite-Repositories
  plans/                Planvalidierung und Planlogik
  runtime/              lokale Runtime-/Modell-Metadaten
  semantics/            validierter semantischer Katalog
  sessions/             temporaere Dokument-Sessions
  sources/              Tabellenquellen, Dokumentchunks und Format-Router
  web/                  lokaler JSON-/HTTP-Transport und Dokument-UI
tests/                  synthetische Tests und Golden Questions
```

## Tests

Mit einem lokal verfuegbaren Python ab Projektstamm:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Der Testlauf liest keine externen Dateien und keine Nutzdaten.

## Datenschutz

- keine Cloud-LLMs oder Cloud-Fallbacks;
- keine Telemetrie;
- llama.cpp nur ueber eine literale Loopback-IP, ohne Proxy oder Redirects;
- keine ungefragten Dateizugriffe;
- persistentes Wissen nur nach ausdruecklicher Bestaetigung;
- Dokumentinhalte standardmaessig nur in temporaeren Sessions;
- ausschliesslich relative Anwendungspfade.

Siehe `SPEC.md` fuer das Zielbild und `PROJECT_STATUS.md` fuer den aktuellen
Migrationsstand. `THIRD_PARTY_ASSETS.md` dokumentiert die geplante lokale
llama.cpp-/GGUF-Bereitstellung und die notwendigen Lizenz- und
Pruefsummenschritte.

## Lizenz und Sicherheit

PortableAgent steht unter der Apache License 2.0. Sicherheitsprobleme bitte
nicht in einem oeffentlichen Issue veroeffentlichen, sondern gemaess
`SECURITY.md` als private Security Advisory melden.
