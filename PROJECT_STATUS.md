# PortableAgent Projektstatus

Stand: 28.09.2026

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
- fachgerechte Stunden-/Minutenanzeige fuer berechnete Dauern;
- Uhrzeitanzeige fuer dezimale Beginn- und Endwerte in Tabellenbelegen;
- sichtbare, lokal erzeugte Zellinhalte zu verwendeten Tabellenzeilen;
- barrierearme Arbeitsanzeige mit reduziertem Bewegungsmodus;
- kompakte Desktop-App-Shell mit einklappbarer Seitennavigation und
  verschiebbarer Tabellenaufteilung;
- lokale Normalisierung eindeutiger Textfilter und sichere Trennung von
  Jahresangaben und Aktionsnamen;
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

Alle **230 synthetischen Unit- und Integrationstests** laufen mit der
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
- Branch-Schutz fuer `main` mit Pull Request, den beiden synthetischen CI-
  Checks und verpflichtender Conversation-Aufloesung; Administrator-Bypass
  bleibt fuer die Einzelbetreuung aktiviert.
- GitHub Secret Scanning mit Push Protection, Dependabot Security Updates und
  private Meldungen von Sicherheitsluecken sind aktiviert.
- Repository-Beschreibung und Topics kennzeichnen das Projekt als lokale,
  offline-first Dokument- und Tabellenanalyse.

## Skill-Recherche und Architekturentscheid

Die oeffentliche Agent-Skills-Spezifikation, OpenAI-Beispiele, Anthropics
Dokument-Skills und `appautomaton/document-SKILLs` wurden auf Workflow,
Abhaengigkeiten, Offline-Eignung und Lizenzlage untersucht. Die Ergebnisse und
Quellen stehen in `SKILL_RESEARCH.md`.

PortableAgent nutzt den `SKILL.md`-Aufbau nur als lokale Verpackungs- und
Dokumentationskonvention. Eine kleine statische Registry wird ausschliesslich
mitgelieferte Skills auf registrierte, typisierte und read-only Capabilities
abbilden. Es gibt keine Skill-Downloads, keine offene Katalogsuche und keine
freie Skript-, Shell- oder Netzwerkausfuehrung. Proprietäre Anthropic-
Dokument-Skills und davon abgeleitete Repositories werden nicht kopiert.
Erste Referenzimplementierung wird `spreadsheet-analysis`; bestehende Parser,
Analyseplaene, Python-Engine und Quellenbelege bleiben Grundlage.

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
2. synthetische Regressionstests fuer aktionsbezogene erste und letzte
   Vorkommen ergaenzen;
3. Entitaetsaufloesung, Filter-vor-Aggregation und Ergebnis-Verifier
   implementieren;
4. darauf die statische Registry und den lokalen
   `spreadsheet-analysis`-Skill aufbauen;
5. v0.1-Release erst nach abgeschlossenem Sicherheits- und Lizenzabgleich
   veroeffentlichen.

## Letzter abgeschlossener Entwicklungsschritt

Die lokale Weboberflaeche ist als kompakter Desktop-Arbeitsbereich mit
einklappbarer Navigation aufgebaut. Dokument- und Tabellenansicht besitzen
nun beide einen verschiebbaren, tastaturbedienbaren Trenner. Tabellenbelege
zeigen die verwendeten Zeileninhalte mit semantisch formatierten Dauern und
Uhrzeiten. Dabei ist nur die erste verwendete Zeile anfangs geöffnet; weitere
Zeilen lassen sich bei Bedarf einzeln aufklappen. Die Tabellenansicht verzichtet
auf einen redundanten Ergebnisplatzhalter und verwendet für die Dateiauswahl
denselben primaeren Schaltflaechenstil wie die übrigen Importbereiche.
Modell- und KI-Dateistatus stehen kompakt und einzeilig im unteren Bereich der
Navigation; im eingeklappten Zustand sind ihre Statuspunkte exakt ausgerichtet.
Das kompakte Markenkennzeichen lautet `PA`. Die obere Leiste bleibt dadurch auf
Kontext und Beenden reduziert. Sichtbare deutsche Meldungen verwenden echte
Umlaute. Bei Minimum und Maximum werden nur die entscheidenden Belegzeilen
ausgegeben, einschließlich aller Gleichstände; Summe und Durchschnitt behalten
alle beitragenden Zeilen.
Eindeutige Fragen nach der Gesamtdauer einer konkret genannten
Aktion in einem Jahr werden lokal deterministisch geplant. Natürliche
Mengenfragen wie `Wieviel Aufwand hatte …?` verwenden den fachlichen
Katalogalias und liefern nur die erfragte Kennzahl, statt zusätzliche
Personalwerte zu summieren. Abweichende Absichten wie Durchschnitt, Minimum
oder Maximum bleiben getrennt. Zellwerte werden dabei nicht an das Modell
weitergegeben. Die vollständige synthetische Testsuite umfasst jetzt 230
erfolgreiche Tests.
