# PortableAgent Spezifikation

Status: Architektur-Baseline fuer v0.1  
Stand: 28.09.2026

## Ziel

PortableAgent ist ein portabler, offline-first KI-Agent zur lokalen Analyse
sensibler PDF-, DOCX-, XLSX/XLSM-, CSV- und TXT-Dateien. Modellinferenz,
Extraktion, Suche, Berechnung und Memory laufen lokal ohne Telemetrie.

## Leitprinzipien

1. **Local-only:** Keine Cloud-LLMs und keine externen Datenuebertragungen.
2. **Belegbarkeit:** Antworten verweisen auf Zeilen, Seiten oder Abschnitte.
3. **Determinismus:** Das Modell erstellt einen Plan; lokale Engines rechnen.
4. **Datensparsamkeit:** Dokumentinhalte bleiben standardmaessig temporaer.
5. **Portabilitaet:** Alle Laufzeitpfade sind relativ zum Projekt.
6. **Modularitaet:** Parser, Agent, Analyse, Memory, Zitate, LLM und UI sind
   ueber schmale Schnittstellen getrennt.

## Zielarchitektur

```text
Lokale Weboberflaeche
        |
     Agent Core
   /      |       \
Sources  Analysis  Memory
Router   Engine    SQLite
  |         |         |
Parser    Python    bestaetigtes
PDF/DOCX Engine     Wissen
XLSX/CSV
  |
Citation Store / SourceRef
        |
lokales llama.cpp + GGUF
```

## Module

### Agent Core

- verwaltet temporaere Sitzungen;
- waehlt Tabellen- oder Dokumentmodus;
- orchestriert Planerstellung, Werkzeuge, Antwort und Belege;
- stellt bei Mehrdeutigkeit Rueckfragen.

### LLM-Adapter

- spricht ausschliesslich mit einem lokalen llama.cpp-Endpunkt;
- fordert strukturierte JSON-Ausgabe an;
- kennt weder Dateisystem noch Analyseausfuehrung;
- besitzt keinen Cloud-Fallback.

### Plans

- typisierte Modelle fuer Filter, Berechnungen, Gruppierung, Sortierung und
  Limits;
- strikte Validierung gegen reale Quellfelder und erlaubte Operationen;
- keine freie Codeausfuehrung.

### Lokale Skills und Capabilities

- projektlokale Skills verwenden den offenen `SKILL.md`-Aufbau als
  Verpackungs- und Dokumentationskonvention;
- eine statische Registry erlaubt nur mitgelieferte, gepruefte Skills und
  ordnet sie registrierten, typisierten Capabilities zu;
- Dateityp und Skill-Familie werden deterministisch gewaehlt, waehrend das
  lokale Modell nur Absicht, Entitaet, Filter und Kennzahl interpretiert;
- Skills koennen weder Shell noch Netzwerk, Paketinstallation, freie
  Dateisystemzugriffe oder schreibende Quelldateioperationen ausloesen;
- Skill-Anweisungen koennen Planvalidierung, Allowlist, Verifier und
  Quellenpflicht nicht erweitern;
- erster Referenz-Skill ist `spreadsheet-analysis`; Details und
  Lizenzentscheidungen stehen in `SKILL_RESEARCH.md`.

### Sources

- Router fuer Tabellen, Fliesstext und gemischte Dokumente;
- Parser fuer XLSX/XLSM, CSV, PDF, DOCX und TXT;
- normalisierte Ausgabe mit stabilen Quellenreferenzen.

### Analysis

- deterministische Python-Engine fuer tabellarische Abfragen in v0.1;
- bei ersten und letzten Vorkommen benannter Aktionen wird die Entitaet lokal
  aufgeloest und gefiltert, bevor `min` beziehungsweise `max` berechnet wird;
- aehnliche Namen und Tippfehler werden nicht still angenommen, sondern als
  typisierte lokale Rueckfrage ausgegeben;
- DuckDB erst spaeter optional, wenn reproduzierbare Leistungstests einen
  konkreten Bedarf belegen;
- reproduzierbare Ergebnisse und explizite Rechenschritte;
- niemals vom LLM frei erzeugten Code ausfuehren.

### Citations

- einheitliches `SourceRef`-Modell fuer Tabellenzeilen und Dokumentstellen;
- Datei, Bereich/Blatt, Zeile beziehungsweise Seite/Abschnitt;
- Antworten ohne ausreichenden Beleg werden als nicht belegt ausgewiesen.

### Memory und Sessions

- SQLite speichert nur Einstellungen, bestaetigtes Wissen und notwendige
  Metadaten;
- Dokumentinhalte und extrahierte Chunks bleiben in temporaeren Sessions;
- persistente Eintraege benoetigen eine ausdrueckliche Benutzeraktion.

## Umfang v0.1

- eigener Agent Core;
- lokaler llama.cpp-Adapter und GGUF-Modell;
- Tabellenmodus mit validierten Plaenen;
- PDF-/DOCX-/TXT-Extraktion;
- SQLite-Memory;
- deterministische Python-Tabellenanalyse;
- Quellen-/Zitationssystem;
- temporaere Dokument-Sessions;
- lokale Weboberflaeche;
- synthetische Unit- und Integrationstests.

Nicht Bestandteil von v0.1 sind Hermes, OpenClaw, PocketBase, Jev, echte
Blockchain, DwarfStar als primaere Engine, Cloud-LLMs sowie automatische
Hardware- und Modellwahl. DuckDB ist keine v0.1-Laufzeitabhaengigkeit und wird
nur bei spaeter nachgewiesenem Leistungsbedarf als optionale Engine bewertet.

## Akzeptanzkriterien v0.1

- Start von unterschiedlichen Laufwerksbuchstaben ohne Codeaenderung.
- Kernbetrieb ohne Internet und ohne ausgehende Anwendungsanfragen.
- Tabellenfragen liefern reproduzierbare Werte und Belegzeilen.
- Dokumentfragen liefern Fundstellen oder eine klare Nicht-gefunden-Antwort.
- Keine Nutzdaten gelangen automatisch ins persistente Memory.
- Alle Standardtests laufen ausschliesslich mit synthetischen Daten.
