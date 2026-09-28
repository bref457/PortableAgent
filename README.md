# PortableAgent

[![Tests](https://github.com/bref457/PortableAgent/actions/workflows/tests.yml/badge.svg)](https://github.com/bref457/PortableAgent/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

PortableAgent ist eine portable, offline-first Anwendung zur lokalen Analyse
von PDF-, DOCX-, TXT-, CSV-, XLSX- und XLSM-Dateien. Modellinferenz,
Dateiverarbeitung, Berechnungen und Memory bleiben auf dem eigenen Rechner.
Es gibt keine Cloud-LLMs, Telemetrie oder Cloud-Fallbacks.

> **Entwicklungsstatus:** v0.1 ist noch nicht veroeffentlicht. Die vorhandenen
> Funktionen und bekannten Grenzen stehen in [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Was PortableAgent bereits kann

- Dokumente und Tabellen nur nach ausdruecklicher Auswahl read-only oeffnen;
- Fragen mit nachvollziehbaren Seiten-, Absatz- oder Zeilenbelegen beantworten;
- Tabellenabfragen ueber validierte Plaene deterministisch berechnen;
- Tabellenoperationen ueber eine feste read-only Capability-Allowlist
  begrenzen und jedes Ergebnis vor der Ausgabe unabhaengig verifizieren;
- ein lokales llama.cpp-Modell ohne Cloud-Verbindung verwenden;
- Dokument-Sessions nur temporaer im Arbeitsspeicher halten;
- bestaetigte Wissensnotizen getrennt in SQLite speichern;
- die Weboberflaeche ausschliesslich an `127.0.0.1` bereitstellen.

## Schnellstart unter Windows

PortableAgent bringt aus Groessen- und Lizenzgruenden keine Python-Runtime,
llama.cpp-Dateien oder Modellgewichte im Repository mit.

1. Repository herunterladen oder klonen.
2. Lokale Komponenten gemaess [THIRD_PARTY_ASSETS.md](THIRD_PARTY_ASSETS.md)
   in `runtime/` und `models/` ablegen.
3. `start.bat --check` ausfuehren.
4. `start.bat` doppelklicken oder in PowerShell starten.
5. Im Browser zuerst die erfundenen Dateien unter `examples/synthetic/`
   ausprobieren.

Bei genau einer erlaubten llama.cpp-Runtime und einem GGUF-Modell startet
`start.bat` beide zusammen mit PortableAgent. Die lokale Oberflaeche ist dann
unter `http://127.0.0.1:8765/` erreichbar. Der Button **PortableAgent beenden**
schliesst Webserver, temporaere Sitzungen und den verwalteten Modellprozess.

## Eigene Dateien verwenden

Eigene Dateien werden direkt ueber den Dateidialog der lokalen Oberflaeche
ausgewaehlt. Sie muessen nicht in das Repository kopiert werden. PortableAgent
durchsucht keine Laufwerke und speichert Dokumentinhalte nicht automatisch
dauerhaft.

Unterstuetzte Formate:

- Dokumente: TXT, DOCX und PDF
- Tabellen: CSV, XLSX und XLSM; bei Excel wird genau ein Tabellenblatt gewaehlt

## Entwicklung

Voraussetzungen sind Python 3.11 oder neuer sowie die in `pyproject.toml`
aufgefuehrten Pakete.

```powershell
python -m pip install -e .
python -m unittest discover -s tests -p "test_*.py"
python -m portable_agent --help
```

Der API-Start mit `python -m portable_agent` bindet standardmaessig nur
`127.0.0.1:8765` und erwartet llama.cpp unter `127.0.0.1:8080`. Er startet
weder einen Browser noch automatisch einen Modellprozess. Einen expliziten
lokalen Modellstart zeigt `python -m portable_agent --help`.

Alle Standardtests arbeiten ausschliesslich mit synthetischen Daten. Hinweise
fuer Beitraege stehen in [CONTRIBUTING.md](CONTRIBUTING.md).

Coding Agents verwenden [AGENTS.md](AGENTS.md) als gemeinsame Regelquelle.
[CLAUDE.md](CLAUDE.md) importiert dieselben Regeln fuer Claude Code, damit
Projektstand, Sicherheitsgrenzen und die Kurzkommandos `update dich` und
`save` bei einem Werkzeugwechsel erhalten bleiben. Die dort definierte
bidirektionale Uebergabe verpflichtet Codex und Claude Code, materielle
Fortschritte vor dem Wechsel in denselben versionierten Status-, Planungs- und
Architekturdateien festzuhalten.

## Projektstruktur

```text
config/                 semantische und technische Konfiguration
examples/synthetic/     erfundene Beispieldaten
src/portable_agent/
  agent/                lokale Workflows und Orchestrierung
  analysis/             deterministische Tabellenberechnung
  capabilities/         statische read-only Operations-Allowlist
  citations/            Quellenmodelle
  llm/                  lokaler llama.cpp-Adapter
  memory/               bestaetigtes SQLite-Wissen
  plans/                Planvalidierung und Policy
  runtime/              lokale Asset- und Prozessverwaltung
  sessions/             temporaere Dokument-Sessions
  sources/              read-only Datei-Adapter
  web/                  lokaler HTTP-Transport und Weboberflaeche
tests/                  synthetische Unit- und Integrationstests
```

## Datenschutz und Sicherheit

- keine Cloud-LLMs, Telemetrie oder externen Analyseanfragen;
- keine ungefragten Dateizugriffe;
- keine Ausfuehrung modellgenerierten Codes, SQLs oder Shell-Befehle;
- persistentes Wissen nur nach ausdruecklicher Bestaetigung;
- Runtime, Modelle, Memory, Sitzungen und Nutzdaten sind von Git ausgeschlossen.

Sicherheitsprobleme bitte nicht als oeffentliches Issue melden. Der vertrauliche
Meldeweg steht in [SECURITY.md](SECURITY.md). Architektur und Grenzen sind in
[SPEC.md](SPEC.md) und [PROJECT_STATUS.md](PROJECT_STATUS.md) dokumentiert.

## Lizenz

PortableAgent steht unter der [Apache License 2.0](LICENSE).
