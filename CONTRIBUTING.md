# Zu PortableAgent beitragen

Danke fuer das Interesse an PortableAgent. Das Projekt befindet sich vor v0.1;
kleine, klar pruefbare Aenderungen sind deshalb besonders willkommen.

## Vor einem Beitrag

- Fuer Fehler und Vorschlaege bitte zuerst die passende Issue-Vorlage nutzen.
- Sicherheitsprobleme ausschliesslich gemaess `SECURITY.md` vertraulich melden.
- Keine echten Dokumente, Tabellen, Zugangsdaten, Modelle, Datenbanken oder
  andere Nutzdaten hochladen.
- Neue Abhaengigkeiten muessen fuer den Kernbetrieb notwendig und offline
  installierbar dokumentiert sein.

## Lokale Einrichtung

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Runtime und Modell sind fuer die synthetischen Standardtests nicht erforderlich.
Hinweise zu einem vollstaendigen lokalen Start stehen in `THIRD_PARTY_ASSETS.md`.

## Aenderungen pruefen

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Tests muessen ausschliesslich synthetische, im Test selbst erzeugte oder bereits
unter `tests/` beziehungsweise `examples/synthetic/` enthaltene Daten nutzen.
Sie duerfen keine externen Dateien oder Nutzdaten lesen.

## Pull Requests

- Eine Aenderung pro Pull Request bevorzugen.
- Verhalten, Sicherheitsfolgen und durchgefuehrte Tests kurz beschreiben.
- Neue oder geaenderte Funktionen mit synthetischen Tests abdecken.
- Oeffentliche Dokumentation und `PROJECT_STATUS.md` bei relevantem
  Projektfortschritt aktualisieren.
- Keine Runtime-Dateien, Modellgewichte, Caches oder lokale Konfigurationen
  einchecken.

Mit einem Beitrag erklaerst du dich damit einverstanden, dass er unter der
Apache License 2.0 veroeffentlicht wird.

