# Lokale Drittanbieter-Assets

PortableAgent arbeitet vollstaendig lokal. Das Git-Repository enthaelt aus
Groessen-, Lizenz- und Sicherheitsgruenden keine ausfuehrbaren Drittanbieter-
Dateien, Modellgewichte oder portable Python-Laufzeit.

## Erwartete Ordner

PortableAgent erkennt lokale Komponenten nur an festen relativen Pfaden:

```text
PortableAgent/
  runtime/
    python/
      python.exe
    llama.cpp/
      llama-server.exe
  models/
    DEIN-MODELL.gguf
```

Diese Ordner sind durch `.gitignore` ausgeschlossen. Dateien darin werden
nicht auf GitHub hochgeladen.

## Was muss bereitgestellt werden?

1. Eine zu Windows passende lokale `llama.cpp`-Serverausgabe aus den
   offiziellen Releases: https://github.com/ggml-org/llama.cpp/releases
2. Ein mit llama.cpp kompatibles Instruct-Modell im GGUF-Format. Fuer die
   portable Baseline eignet sich ein Modell der 4B-Klasse in einer kompakten
   Quantisierung wie `Q4_K_M`.
3. Entweder eine lokale Python-Installation gemaess `pyproject.toml` oder eine
   vorbereitete portable Python-Laufzeit unter `runtime/python/`.

Vor der Verwendung muessen Downloadquelle, Modellkarte, Lizenz und enthaltene
Drittanbieterhinweise geprueft werden. PortableAgent laedt keine dieser
Komponenten automatisch herunter und besitzt keinen Online-Updater.

## Automatische lokale Erkennung

Sind genau eine erlaubte llama.cpp-Runtime und genau ein GGUF-Modell vorhanden,
kann `start.bat` beide automatisch starten. Der Modellserver wird nur an
`127.0.0.1` gebunden. Fehlende oder mehrere Kandidaten fuehren zu einer klaren
Fehlermeldung; PortableAgent trifft keine willkuerliche Auswahl.

Die Erkennung kann ohne Serverstart kontrolliert werden:

```powershell
.\start.bat --list-local-assets
.\start.bat --check
```

## Eigene Dokumente und Tabellen

Nutzdaten gehoeren nicht in `runtime/`, `models/` oder andere Projektordner.
Nach dem lokalen Start werden sie direkt ueber den Dateidialog der
Weboberflaeche ausgewaehlt:

- Dokumente: TXT, DOCX oder PDF
- Tabellen: CSV, XLSX oder XLSM; bei Excel wird genau ein Reiter gewaehlt

Die ausgewaehlte Datei wird nur an den lokalen Dienst auf `127.0.0.1`
uebergeben und read-only verarbeitet. PortableAgent durchsucht keine
Laufwerke, importiert keine Dateien automatisch und speichert Dokumentinhalte
nicht automatisch dauerhaft.

## Sicherer erster Test

Die Dateien unter `examples/synthetic/` enthalten ausschliesslich erfundene
Testdaten. Mit `einsaetze.csv` kann der Tabellenmodus und mit
`projektinfo.txt` der Dokumentmodus ausprobiert werden, bevor eigene Dateien
verwendet werden.

## Pruefung nach der Einrichtung

1. Runtime, Modell und jeweilige Lizenztexte lokal ablegen.
2. `start.bat --list-local-assets` ausfuehren.
3. `start.bat --check` ausfuehren.
4. PortableAgent starten und die synthetischen Beispieldateien testen.
5. Die Anwendung ueber `PortableAgent beenden` kontrolliert herunterfahren.

Lokale Komponenten werden bei Aktualisierungen zuerst separat geprueft.
Vorhandene Assets oder Nutzdaten werden niemals automatisch ueberschrieben.
