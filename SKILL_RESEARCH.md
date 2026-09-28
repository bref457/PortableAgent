# Recherche und Architekturentscheid zu lokalen Skills

Stand: 28.09.2026

## Ergebnis in Kurzform

PortableAgent uebernimmt den offenen Aufbau eines Agent Skills als
Ordnungs- und Dokumentationskonvention, nicht jedoch ein fremdes
Ausfuehrungsframework. Skills werden lokal mit dem Projekt ausgeliefert,
vorab geprueft und auf registrierte, typisierte, read-only Capabilities
abgebildet. Sie duerfen weder Shell noch Netzwerk, Paketinstallation oder
freie Dateisystemzugriffe ausloesen.

Der erste Skill wird `spreadsheet-analysis`. Er nutzt die vorhandenen
Tabellenquellen, typisierten Analyseplaene, die deterministische Python-Engine
und `SourceRef`. Neue Tabellenbibliotheken oder Office-Programme sind dafuer
nicht erforderlich.

## Untersuchte Quellen

| Quelle | Lizenzlage | Relevante Muster | Eignung und Entscheidung |
| --- | --- | --- | --- |
| [OpenAI: Skills in Codex](https://developers.openai.com/plugins/concepts/skills) und [Tool Skills](https://developers.openai.com/api/docs/guides/tools-skills) | Produktdokumentation; einzelne veroeffentlichte Skills besitzen eigene Lizenzen | `SKILL.md`, optionale Referenzen/Skripte/Assets, stufenweises Laden, Skills als Workflow- statt Tool-Schicht | Strukturprinzipien verwenden. Keine gehosteten Skills, API-Laufzeit oder offenen Kataloge in PortableAgent. |
| [OpenAI Skills Catalog](https://github.com/openai/skills) und [PDF-Skill](https://github.com/openai/skills/tree/main/skills/.curated/pdf) | Lizenz ist je Skill zu pruefen; der untersuchte PDF-Skill ist Apache-2.0 | Extraktion und visuelle Darstellung getrennt behandeln; Ergebnisse nach der Verarbeitung pruefen | Nur Architektur- und Pruefprinzipien. Der Skill installiert Werkzeuge und schreibt Artefakte und ist daher keine PortableAgent-Laufzeitkomponente. |
| [OpenAI Agents Python: CSV Workbench](https://github.com/openai/openai-agents-python/tree/main/examples/tools/skills/csv-workbench) | Repository-Lizenz MIT | Schema zuerst erfassen, Berechnungen reproduzierbar ausfuehren, knappe numerische Ergebnisse | Konzeptuell passend. Keine Ausfuehrung von modellgeneriertem Python; die vorhandene typisierte Engine bleibt massgeblich. |
| [Agent Skills Specification](https://github.com/agentskills/agentskills/blob/main/docs/specification.mdx) und [Client Implementation](https://github.com/agentskills/agentskills/blob/main/docs/client-implementation/adding-skills-support.mdx) | Code und Spezifikation Apache-2.0; Dokumentation laut Repository CC-BY-4.0 | Ordner mit `SKILL.md`; Metadaten, Instruktionen und Ressourcen stufenweise laden; optionale `scripts`, `references`, `assets` | Als kompatible Verpackungs- und Metadatenkonvention verwenden. Experimentelle Felder und frei ausfuehrbare Skripte bleiben ausserhalb des Umfangs. |
| [Anthropic Skills](https://github.com/anthropics/skills) mit XLSX, PDF, DOCX und PPTX | Diese vier Dokument-Skills sind ausdruecklich source-available, nicht Open Source; Kopieren, Ableitungen und Weitergabe sind eingeschraenkt | Umfangreiche Dokument-Workflows, Werkzeugketten und Qualitaetskontrollen | Ausschliesslich Markt- und Konzeptvergleich. Kein Text, Code oder Asset wird uebernommen oder abgeleitet. |
| [appautomaton/document-SKILLs](https://github.com/appautomaton/document-SKILLs) | Repository nennt MIT; README bezeichnet die Inhalte zugleich als von Anthropic adaptiert | Aufteilung nach Dateityp, Formel- und Ausgabepruefung, kombinierte Dokumentwerkzeuge | Wegen der erklaerten Herkunft und der restriktiven Upstream-Lizenz keine Wiederverwendung. Zusaetzlich unpassend durch automatische Paketinstallation, Systemwerkzeuge und schreibende Workflows. |

## Was PortableAgent bewusst nicht uebernimmt

- keine Cloud-API fuer Skills und kein Cloud-LLM;
- kein automatisches Installieren oder Aktualisieren von Skills;
- keine Suche in globalen oder benutzergesteuerten Skill-Verzeichnissen;
- keine `uv`, `pip`- oder `npm`-Aufrufe waehrend der Anwendung;
- keine frei ausfuehrbaren Skill-Skripte, Shell-Kommandos, SQL-Fragmente oder
  modellgenerierten Python-Programme;
- keine automatischen Schreib-, Konvertierungs- oder Reparaturvorgaenge an
  Quelldateien;
- keine Uebernahme proprietaerer oder lizenzrechtlich zweifelhafter Inhalte.

## Beschlossene Architektur

```text
Dateityp und normalisierte Struktur
        -> deterministischer Skill-Router
        -> gepruefte lokale Skill-Metadaten
        -> typisierter Analyseplan
        -> statische Capability Registry
        -> vorhandene read-only Python-Implementierung
        -> deterministischer Verifier
        -> Ergebnis mit SourceRef-Belegen
```

### Skill-Paket

Ein auslieferbarer Skill besitzt einen projektlokalen Ordner und eine kurze
`SKILL.md` mit mindestens `name` und `description`. Referenzen duerfen als
statische Projektressourcen hinzukommen. In der ersten Ausbaustufe werden
keine `scripts` aus einem Skill ausgefuehrt.

Die Anwendung scannt nicht beliebige Ordner. Eine statische Registry nennt
explizit die mitgelieferten Skills, ihre Version, erlaubte Quelldateitypen und
Capabilities. Dadurch ist die installierte Funktionalitaet pruefbar und der
Prompt fuer das kleine lokale Modell bleibt knapp.

### Auswahl und Prompting

Der Dateityp entscheidet deterministisch ueber die moegliche Skill-Familie.
Das lokale Modell interpretiert innerhalb dieses Rahmens Absicht, Entitaet,
Filter und Kennzahl und liefert weiterhin nur einen typisierten Plan. Zuerst
werden nur Name, Beschreibung und erlaubte Capabilities eines Skills geladen;
ausfuehrlichere, gepruefte Hinweise folgen erst nach der Auswahl.

Skill-Text und Dokumentinhalt sind Daten, keine hoeher priorisierten
Systemanweisungen. Ein Skill kann die Registry, Planvalidierung oder
Sicherheitsgrenzen nicht erweitern.

### Erste Capabilities

- `table.inspect`
- `table.resolve_entity`
- `table.filter`
- `table.aggregate`
- `table.first_occurrence`
- `table.last_occurrence`
- `table.source_rows`
- `result.verify`

Die Registry beschreibt nur Berechtigungen und Zuordnungen. Die Implementierung
bleibt in normalen Python-Modulen mit typisierten Ein- und Ausgaben. Die
vorhandenen Abhaengigkeiten `openpyxl` und `pypdf` genuegen fuer den ersten
Ausbau.

### Verifier

Der Verifier arbeitet ausserhalb des Modells. Fuer eine Frage nach dem ersten
oder letzten Auftreten einer benannten Aktion prueft er insbesondere:

1. Die Entitaet wurde gegen tatsaechliche Tabellenwerte eindeutig aufgeloest.
2. Der Plan enthaelt den zugehoerigen Filter.
3. Nur passende Zeilen gelangen in die Berechnung.
4. `min` oder `max` wird nach dem Filter angewendet.
5. Ergebnis, entscheidende Zeile und `SourceRef` stimmen ueberein.
6. Mehrdeutige, fehlende oder ungueltige Daten erzeugen keine Ersatzantwort.

## Warum kein allgemeines Skill-Framework

PortableAgent besitzt bereits die sicherheitskritischen Bausteine: read-only
Quellen, typisierte Plaene, eine deterministische Tabellenengine,
Quellenbelege, temporaere Dokument-Sessions und einen auf Loopback begrenzten
Modelladapter. Ein allgemeines Framework wuerde vor allem neue
Ausfuehrungswege, Abhaengigkeiten und Angriffsoberflaeche schaffen. Eine kleine
Registry macht dagegen die wiederverwendbaren Workflows sichtbar, ohne diese
Grenzen zu umgehen.

## Naechste Implementierungsmigration

Die Regressionstests, Entitaetsaufloesung, Filter-vor-Aggregation, der
deterministische Ergebnis-Verifier und die statische Capability Registry sind
abgeschlossen. Als naechste Migrationen folgen:

1. Verhalten mit kontrollierten Generatoren und dem lokalen Qwen-Modell
   vergleichen; unzuverlaessige Schritte bleiben deterministisch.
2. Darauf den projektlokalen `spreadsheet-analysis`-Skill aufbauen.

## Abnahmekriterien

- vollstaendiger Betrieb ohne Netzwerkzugriff;
- keine neuen Laufzeitabhaengigkeiten fuer den ersten Skill;
- keine freie Code- oder Skriptausfuehrung;
- ausschliesslich synthetische Testdaten;
- gleiche typisierte Plaene fuer gleichbedeutende Kernfragen;
- klare Rueckfragen oder Nicht-gefunden-Zustaende statt Raten;
- jede dateibasierte Antwort stimmt mit ihren lokalen Belegen ueberein.
