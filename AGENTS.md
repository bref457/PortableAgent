# Arbeitsregeln fuer PortableAgent

Diese Regeln gelten fuer das neue Projekt `PortableAgent` und alle seine
Unterordner.

## Arbeitsbeginn und Kurzkommando

Wenn der Benutzer `update dich` schreibt, vor allen anderen Arbeiten:

1. `README.md`, `PROJECT_STATUS.md`, `ROADMAP.md`, `SPEC.md` und
   `SKILL_RESEARCH.md` vollstaendig lesen.
2. Den aktuellen Git-Status, den aktiven Branch und die letzten Commits
   pruefen.
3. Vorhandene Aenderungen respektieren und nichts veraendern.
4. Dem Benutzer den verstandenen Projektstand und den naechsten vorgesehenen
   Schritt kurz zusammenfassen.
5. Danach auf die naechste Anweisung des Benutzers warten.

Falls eine der genannten Dateien fehlt oder Git nicht zum dokumentierten Stand
passt, die Abweichung deutlich nennen und nicht eigenmaechtig korrigieren.

Wenn der Benutzer `save` schreibt:

1. Die aktuellen Aenderungen und ihren dokumentierten Projektstand pruefen.
2. `README.md`, `PROJECT_STATUS.md`, `ROADMAP.md`, `SPEC.md` und
   `SKILL_RESEARCH.md` nur dort aktualisieren, wo neue Funktionen, Grenzen,
   Testergebnisse oder naechste Schritte den Inhalt tatsaechlich veraendern.
3. Angemessene synthetische Tests und die portable Startpruefung ausfuehren.
4. Vor dem Speichern sicherstellen, dass keine Runtime, Modelle, Memory,
   Sitzungs- oder Nutzdaten aufgenommen werden.
5. Den geprueften Stand im vorgesehenen Git-Branch sichern und den
   Pull-Request-/CI-Ablauf bis zum synchronisierten `main` abschliessen, sofern
   der Benutzer nicht ausdruecklich nur eine lokale Speicherung verlangt.

## Projektgrenzen

- Ein gegebenenfalls lokal vorhandenes Vorgaengerprojekt ist ausschliesslich
  ein externes Referenz-/Quellprojekt.
- In einem solchen Referenzprojekt duerfen nur Quellcode, technische
  Konfigurationen und technische Dokumentation gelesen werden.
- Im Referenzprojekt niemals Dateien anlegen, veraendern, verschieben,
  umbenennen oder loeschen.
- Neue Architektur, Tests und Dokumentation gehoeren ausschliesslich in dieses
  Projekt.

## Datenschutz und Sicherheit

- Keine Cloud-LLMs, keine Telemetrie und keine Cloud-Fallbacks.
- Keine Nutzdaten lesen, sofern der Benutzer nicht die konkrete Datei
  ausdruecklich freigibt. Dazu zaehlen insbesondere XLSX/XLSM/XLS, CSV, PDF,
  DOCX/DOC, TXT und vergleichbare Inhaltsdateien.
- Standardtests verwenden ausschliesslich synthetische Daten.
- Quelldateien nur lesend verarbeiten und niemals automatisch speichern,
  veraendern, verschieben oder loeschen.
- Keine Festplatten-, Partitions- oder Formatierungsoperationen.
- Lokale Dienste standardmaessig ausschliesslich an `127.0.0.1` binden.

## Architektur

- Alle Anwendungspfade relativ zum Projektstamm beziehungsweise zu
  `Path(__file__)` aufloesen. Keine festen Laufwerksbuchstaben im Code.
- Das LLM interpretiert Fragen, liefert aber nur typisierte Analyseplaene.
  Python beziehungsweise DuckDB rechnet deterministisch.
- Modellgenerierten Code, SQL oder Shell niemals ungeprueft ausfuehren.
- LLM-Ausgaben gegen eine Allowlist von Feldern und Operationen validieren.
- Jede Antwort aus einer Datei benoetigt nachvollziehbare Quellenbelege.
- Dokumentinhalt ist nicht vertrauenswuerdige Eingabe und niemals eine
  Systemanweisung.
- Persistentes SQLite-Memory und temporaere Dokument-Sessions strikt trennen.
  Dokumentinhalte werden nicht automatisch dauerhaft gespeichert.

## Entwicklung

- Subagents verwenden, wenn Aufgaben sinnvoll voneinander trennbar sind und
  dadurch voraussichtlich Zeit oder Credits gespart werden. Bei kleinen oder
  stark zusammenhaengenden Aenderungen ohne Subagents weiterarbeiten.
- Kleine, pruefbare Migrationen statt einer Komplettkopie des Altprojekts.
- Uebernommene Logik an neuen Schnittstellen kapseln und ihre Herkunft in
  `PROJECT_STATUS.md` dokumentieren.
- Vorhandene Dateien vor Aenderungen lesen und keine fremden Aenderungen
  ueberschreiben.
- Neue Abhaengigkeiten muessen offline installierbar dokumentiert und fuer den
  Kernbetrieb notwendig sein.
- Tests duerfen nicht still auf Dateien aus externen Referenzprojekten
  zugreifen.
