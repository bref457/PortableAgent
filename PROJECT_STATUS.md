# PortableAgent Projektstatus

Stand: 27.09.2026

## Status

PortableAgent befindet sich in der Entwicklung zu v0.1. Das Projekt ist als
eigenstaendige, portable und offline-first Anwendung aufgebaut. Ein frueheres
lokales Tabellenprojekt diente ausschliesslich als technische Referenz und ist
weder Laufzeitabhaengigkeit noch Bestandteil dieses Repositories.

## Implementiert

- typisierte Analyseplaene mit strikter JSON- und Allowlist-Validierung;
- deterministische Python-Tabellenengine fuer Filter, Aggregationen,
  Gruppierung, Sortierung und Limits;
- read-only Tabellenquellen fuer CSV, XLSX und XLSM;
- read-only Dokumentquellen fuer TXT, DOCX und PDF;
- lokale lexikalische Dokumentensuche mit stabilen Quellenbelegen;
- getrennte Tabellen- und Dokument-Workflows;
- rein fluechtige Dokument-Sessions;
- bestaetigtes SQLite-Memory ohne automatische Dokumentpersistenz;
- lokaler llama.cpp-Adapter ohne Cloud-Fallback;
- strikt auf Loopback begrenzter HTTP-Server;
- kontrollierter Start und Shutdown eines eigenen llama.cpp-Kindprozesses;
- lokale Weboberflaeche fuer Dokumente, Tabellen und Memory;
- portable Windows-Startdiagnose und relative Anwendungspfade;
- synthetische Beispieltabellen und -dokumente unter `examples/synthetic/`.

## Sicherheits- und Datenschutzgrenzen

- keine Cloud-LLMs, Telemetrie oder externen Analyseanfragen;
- lokale Dienste binden standardmaessig ausschliesslich an `127.0.0.1`;
- Quelldateien werden read-only verarbeitet und nicht automatisch veraendert;
- Nutzdaten werden nicht automatisch gesucht, importiert oder gespeichert;
- Modellgenerierter Code, SQL und Shell werden nicht ausgefuehrt;
- Modellplaene werden gegen bekannte Felder und Operationen validiert;
- Antworten aus Dateien enthalten nachvollziehbare Quellenbelege;
- Dokumentinhalt gilt immer als nicht vertrauenswuerdige Eingabe;
- persistentes Wissen benoetigt eine ausdrueckliche Bestaetigung;
- Runtime, Modelle, Memory, Sitzungsdaten und Nutzdaten sind von Git
  ausgeschlossen.

## Verifikation

Alle **218 synthetischen Unit- und Integrationstests** laufen mit der
portablen Projektlaufzeit erfolgreich. `start.bat --check` bestaetigt die
portable Runtime. Die Tests lesen keine externen Dateien und keine Nutzdaten.

Die Testabdeckung umfasst unter anderem:

- Plan-Decoding und semantische Policy;
- deterministische Tabellenberechnungen und Zeilenbelege;
- Parserlimits und unveraenderte synthetische Quelldateien;
- Dokument-Retrieval, Fundstellen und Nicht-gefunden-Antworten;
- Session- und Memory-Lebenszyklus;
- lokale HTTP-, Host-, Content-Type- und Groessengrenzen;
- Modellfehler, Asset-Erkennung, Startplan und kontrollierten Shutdown;
- Release-Ausschluesse mit echter Git-Regelauswertung.

## Gezielt uebernommene Konzepte

Aus dem technischen Referenzprojekt wurden nur klar abgegrenzte Konzepte neu
implementiert:

- `LLM -> validierter Analyseplan -> lokale Berechnung -> Beleg`;
- semantische Felddefinitionen und Aliasstruktur;
- erlaubte Filter- und Aggregationsoperationen;
- strukturierte JSON-Ausgabe am lokalen Modellendpunkt;
- Golden Questions als Regressionseingaben;
- explizite Rueckfragen bei mehrdeutigen Kennzahlen.

Monolithische Skripte, konkrete Nutzdatenpfade, Sitzungsinhalte und persistente
Dokumentdaten wurden nicht uebernommen.

## Release-Basis

- Lizenz: Apache-2.0;
- Sicherheitsrichtlinie: `SECURITY.md`;
- Drittanbieter- und Asset-Anleitung: `THIRD_PARTY_ASSETS.md`;
- synthetischer Einstieg: `examples/synthetic/README.md`;
- Beitragsrichtlinie sowie Issue- und Pull-Request-Vorlagen;
- GitHub Actions fuer synthetische Tests unter Python 3.11 und 3.13;
- woechentliche Dependabot-Pruefung fuer Python- und Actions-Abhaengigkeiten;
- oeffentliche GitHub-Veroeffentlichung ohne Runtime-, Modell- oder
  Nutzdatendateien.

## Aktuelle Grenzen

- llama.cpp-Runtime, GGUF-Modell und portable Python-Laufzeit werden nicht aus
  GitHub geladen und muessen lokal bereitgestellt werden;
- es gibt keinen automatischen Download und keinen Online-Updater;
- die automatische Asset-Auswahl verlangt genau eine erlaubte Runtime und
  genau ein Modell;
- eine manuelle Modellauswahl und Hardwareentscheidung in der Weboberflaeche
  sind noch nicht implementiert;
- der physische Portabilitaets-Smoke-Test auf einem zweiten Windows-System
  beziehungsweise unter einem anderen Laufwerksbuchstaben steht noch aus.

## Naechste Schritte

1. physischen Portabilitaets-Smoke-Test durchfuehren;
2. GitHub-Repository-Metadaten und Branch-Schutz nach erster erfolgreicher
   CI-Ausfuehrung konfigurieren;
3. private Vulnerability-Reporting-Funktion in GitHub pruefen;
4. v0.1-Release erst nach abgeschlossenem Sicherheits- und Lizenzabgleich
   veroeffentlichen.

## Letzter abgeschlossener Entwicklungsschritt

Die oeffentliche Repository-Basis wurde vervollstaendigt: Die README fuehrt
kompakt von den Projektgrenzen ueber den Windows-Schnellstart bis zur Auswahl
eigener Dateien. Geraetespezifische Referenzpfade wurden aus der oeffentlichen
Dokumentation entfernt. `CONTRIBUTING.md`, strukturierte Issue-Vorlagen und eine
Pull-Request-Checkliste verhindern insbesondere das versehentliche Hochladen
echter Nutzdaten. Paket-Metadaten enthalten nun Projektlinks, Status,
Python-Versionen und Suchbegriffe.

GitHub Actions prueft die synthetische Testsuite unter Python 3.11 und 3.13;
Dependabot beobachtet Python- und Workflow-Abhaengigkeiten. Lokal liefen alle
218 synthetischen Tests sowie `start.bat --check` erfolgreich. Runtime, Modell,
persistentes Memory, temporaere Sitzungen, Nutzdaten und Python-Caches bleiben
von Git ausgeschlossen.

