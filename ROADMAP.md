# PortableAgent Entwicklungsplan

Stand: 28.09.2026

## Ausgangslage

- Der lokale Projektstamm ist der massgebliche aktuelle Entwicklungsstand.
- Die lokale synthetische Testsuite umfasst 230 erfolgreiche Tests.
- Der lokale 230-Test-Stand wurde nachvollziehbar wieder in Git aufgenommen,
  per Pull Request geprueft und in `main` zusammengefuehrt.
- Runtime, Modell, Memory, Sitzungsdaten und Nutzdaten bleiben von Git
  ausgeschlossen.
- GitHub-Sicherheitsfunktionen, Branch-Schutz und Repository-Topics sind
  eingerichtet. Zugangsdaten werden niemals in Projektdokumenten gespeichert.

## Fortschritt

- Phase 1 ist abgeschlossen.
- Phase 2 ist abgeschlossen und in `SKILL_RESEARCH.md` dokumentiert.
- Phase 3 ist entschieden: eine kleine statische Capability Registry und
  projektlokale, gepruefte Skills statt eines allgemeinen
  Ausfuehrungsframeworks.
- Naechster Entwicklungsschritt ist Phase 4.

## Verbindliche Leitlinien

- Produktive Nutzung bleibt vollstaendig lokal und offline.
- Keine Cloud-LLMs, Telemetrie, Cloud-Fallbacks oder automatischen Downloads.
- Quelldateien werden nur nach ausdruecklicher Auswahl und ausschliesslich
  read-only verarbeitet.
- Das lokale LLM interpretiert Fragen und erzeugt hoechstens typisierte Plaene.
- Python fuehrt Filter, Berechnungen und Validierungen deterministisch aus.
- Modellgenerierter Code, SQL oder Shell wird nicht ausgefuehrt.
- Belastbare Antworten benoetigen nachvollziehbare lokale Belege.
- Bei Mehrdeutigkeit wird rueckgefragt und nicht geraten.
- Bestehender funktionierender Code wird bevorzugt weiterentwickelt.
- Fremde Skills gelten bis zur Pruefung als nicht vertrauenswuerdig.

## Phase 1: Git wiederherstellen und lokalen Stand sichern

1. GitHub-Anmeldung fuer `bref457` im Browser erneuern.
2. Git-Metadaten im lokalen Projektstamm wiederherstellen, ohne Arbeitsdateien
   zu ersetzen oder zurueckzusetzen.
3. `origin` mit `https://github.com/bref457/PortableAgent.git` verbinden und
   `origin/main` als belegten Ausgangspunkt verwenden.
4. Einen Arbeitsbranch wie `recovery/local-230-test-baseline` anlegen.
5. Zeilenenden normalisieren beziehungsweise so konfigurieren, dass reine
   LF-/CRLF-Unterschiede nicht als fachliche Aenderungen erscheinen.
6. Aenderungen, Git-Ausschluesse und gestagte Dateien auf Runtime, Modelle,
   Memory, Nutzdaten, Caches und lokale Konfigurationen pruefen.
7. Die 230 synthetischen Tests und `start.bat --check` erneut ausfuehren.
8. Den lokalen Entwicklungsstand in einem nachvollziehbaren Commit sichern.
9. Den Branch pushen, einen Pull Request gegen `main` erstellen und die CI-
   Pruefungen abwarten.
10. Erst nach erfolgreicher Pruefung zusammenfuehren. Noch keinen Release-Tag
    und keine voreilige Versionsaenderung erstellen.

## Phase 2: Bestehende Skills recherchieren

Gezielt untersucht werden insbesondere:

- OpenAI Skills und Dokument-Workflows;
- die offene Agent-Skills-Spezifikation;
- Anthropic-Skills fuer XLSX, PDF, DOCX und PPTX;
- `appautomaton/document-SKILLs`;
- weitere serioese Skills fuer Tabellenanalyse, Retrieval, Provenance,
  Validierung und Ambiguitaetsbehandlung.

Fuer jede Quelle werden mindestens festgehalten:

- Quelle und konkreter Skill;
- Lizenz und erlaubte Nutzung;
- Zweck und interessanter Workflow;
- benoetigte Tools und Abhaengigkeiten;
- Netzwerkzugriffe, Telemetrie, Downloads und Schreiboperationen;
- lokale Offline-Eignung;
- passende Konzepte fuer PortableAgent;
- Entscheidung: uebernehmen, selbst implementieren oder nur als Referenz
  verwenden.

Proprietaere oder unklare Skills werden nicht kopiert oder abgeleitet. Ihre
Konzepte duerfen nur als Vergleich fuer eine eigenstaendige Implementierung
dienen.

## Phase 3: Kleine lokale Skill-Architektur entscheiden

Die Recherche soll zeigen, ob und in welchem Umfang ein eigener Skill-Layer
einen messbaren Vorteil bringt. Der bevorzugte Zielablauf ist:

```text
Dateityp und Struktur
        -> deterministische Skill-Auswahl
        -> lokale Skill-Anweisungen
        -> typisierter Plan
        -> registrierte Python-Tools
        -> Verifier
        -> Antwort mit Belegen
```

Rahmenbedingungen:

- Skills werden mit dem Projekt lokal ausgeliefert und nie automatisch
  heruntergeladen.
- Endbenutzer koennen keine beliebigen Skills aus offenen Katalogen laden.
- Skills erhalten keine freie Shell-, Netzwerk- oder Dateisystemausfuehrung.
- Nur registrierte, typisierte und read-only Faehigkeiten sind erlaubt.
- Dateityp und grobe Skill-Auswahl bleiben moeglichst deterministisch.
- Skill-Inhalt ist nicht automatisch vertrauenswuerdiger als eine
  Benutzeranweisung.
- Zunaechst wird eine kleine statische Registry gegen ein groesseres Framework
  bewertet.

## Phase 4: Excel als Referenzimplementierung stabilisieren

Der erste Workflow ist `spreadsheet-analysis`. Zuerst entstehen synthetische
Regressionstests fuer natuerliche Varianten wie:

- `Wann war Aktion XY das erste Mal?`
- `Wann sind wir XY erstmals gefahren?`
- `Wann fand XY zum ersten Mal statt?`
- `An welchem Datum wurde XY erstmals durchgefuehrt?`

Zusaetzlich werden aehnliche Namen, mehrere Treffer, keine Treffer,
Tippfehler, unterschiedliche Jahre, fehlende Werte und mehrere Worksheets
abgedeckt.

Der verbindliche Ablauf fuer erste und letzte Vorkommen lautet:

```text
Entitaet erkennen
    -> eindeutigen Tabellenwert lokal aufloesen
    -> bei Mehrdeutigkeit rueckfragen
    -> passende Zeilen filtern
    -> innerhalb der Treffer min/max berechnen
    -> entscheidende Belegzeilen bestimmen
    -> Ergebnis gegen Filter und Belege validieren
```

Damit wird insbesondere verhindert, dass fuer eine konkrete Aktion versehentlich
das frueheste Datum einer anderen Aktion ausgegeben wird.

## Phase 5: Capability Registry und Verifier

Nur tatsaechlich benoetigte Faehigkeiten werden registriert, beispielsweise:

- `table.inspect`
- `table.filter`
- `table.aggregate`
- `table.first_occurrence`
- `table.last_occurrence`
- `table.source_rows`

Der Verifier prueft mindestens:

- die aufgeloeste Entitaet ist eindeutig;
- der notwendige Entitaetsfilter ist im Plan enthalten;
- alle ausgewerteten Zeilen erfuellen den Filter;
- `min`, `max`, `sum` oder `average` wurden erst nach dem Filter angewendet;
- Ergebnis und Belegzeilen stimmen ueberein;
- eine fehlgeschlagene Validierung erzeugt keine plausible Ersatzantwort.

## Phase 6: Lokales Modell evaluieren

Die neuen Workflows werden sowohl mit kontrollierten Testgeneratoren als auch
mit dem vorhandenen lokalen Qwen-Modell geprueft. Bewertet werden:

- konsistente Skill- und Intent-Erkennung;
- gleiche Plaene fuer gleichbedeutende Formulierungen;
- ungueltige oder widerspruechliche Modellplaene;
- Ambiguitaet und Nicht-gefunden-Faelle;
- Uebereinstimmung von Antwort, Berechnung und Beleg;
- sicheres Verhalten ohne erreichbaren Modellprozess.

Aufgaben, die das lokale Modell nicht ausreichend zuverlaessig loest, bleiben
oder werden deterministisch implementiert.

## Phase 7: Offline- und Sicherheitsnachweis

- Quellcode und Assets auf externe Netzwerkpfade pruefen.
- Nur Loopback-Kommunikation zum lokalen llama.cpp-Endpunkt erlauben.
- Keine externen Fonts, CDNs, Updatechecks oder Modell-Downloads.
- Skill- und Tool-Allowlist mit Negativtests pruefen.
- Keine Nutzdaten in Logs, Git, Memory oder Standardtests.
- Normale Nutzung mit blockiertem Internet testen.
- Neue Abhaengigkeiten nur aufnehmen, wenn sie fuer den Kernbetrieb notwendig,
  lokal mitlieferbar und lizenzrechtlich geklaert sind.

## Phase 8: Weitere Dokument-Skills

Erst nach der stabilen Excel-Referenz werden die Prinzipien schrittweise auf
TXT, PDF und DOCX sowie spaeter gegebenenfalls PPTX uebertragen. Das bestehende
Dokument-Retrieval und das gemeinsame `SourceRef`-Modell bleiben Grundlage.

Moegliche Erweiterungen sind:

- belegte Dokumentzusammenfassungen;
- Fragen zu Seiten- oder Abschnittsbereichen;
- Entitaets-, Termin- und Datumssuche;
- hierarchische Zusammenfassung langer Dokumente;
- Widerspruchssuche;
- klare Nicht-gefunden- und Unzureichende-Daten-Zustaende.

## Phase 9: Versionierung

Der wiederhergestellte 230-Test-Stand bleibt zunaechst `0.1.0.dev0`. Eine neue
Version wird erst nach festgelegtem Umfang vergeben:

- isolierte Korrekturen: passende kleine Entwicklungsversion;
- lokaler Skill-/Capability-Layer plus stabile Excel-Referenz: voraussichtlich
  `0.2.0.dev0`.

Ein Release-Tag wird erst nach Sicherheits-, Lizenz-, Offline- und
Portabilitaetspruefung erstellt.

## Naechster konkreter Schritt

Phase 4 beginnt mit synthetischen Regressionstests fuer aktionsbezogene erste
und letzte Vorkommen. Danach folgen Entitaetsaufloesung,
Filter-vor-Aggregation und der Ergebnis-Verifier. Die kleine Registry wird
erst auf diesem geprueften Workflow aufgebaut.
