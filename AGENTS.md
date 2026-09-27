# Arbeitsregeln fuer PortableAgent

Diese Regeln gelten fuer das neue Projekt `PortableAgent` und alle seine
Unterordner.

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

- Kleine, pruefbare Migrationen statt einer Komplettkopie des Altprojekts.
- Uebernommene Logik an neuen Schnittstellen kapseln und ihre Herkunft in
  `PROJECT_STATUS.md` dokumentieren.
- Vorhandene Dateien vor Aenderungen lesen und keine fremden Aenderungen
  ueberschreiben.
- Neue Abhaengigkeiten muessen offline installierbar dokumentiert und fuer den
  Kernbetrieb notwendig sein.
- Tests duerfen nicht still auf Dateien aus externen Referenzprojekten
  zugreifen.

