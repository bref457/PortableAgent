import sys
import re
import unittest
from importlib.resources import files
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))


class StaticUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        static = files("portable_agent.web").joinpath("static")
        cls.html = static.joinpath("index.html").read_text(encoding="utf-8")
        cls.javascript = static.joinpath("app.js").read_text(encoding="utf-8")
        cls.css = (
            static.joinpath("app.css").read_text(encoding="utf-8")
            + static.joinpath("modes.css").read_text(encoding="utf-8")
        )

    def test_document_and_table_modes_are_explicit_accessible_tabs(self):
        self.assertIn('role="tablist"', self.html)
        self.assertIn('id="document-tab"', self.html)
        self.assertIn('aria-controls="document-mode"', self.html)
        self.assertIn('id="table-tab"', self.html)
        self.assertIn('aria-controls="table-mode"', self.html)
        self.assertIn('id="table-mode"', self.html)
        self.assertIn('id="memory-tab"', self.html)
        self.assertIn('aria-controls="memory-mode"', self.html)
        self.assertIn('id="memory-mode"', self.html)
        self.assertIn('id="model-status"', self.html)
        self.assertIn('id="model-status-text"', self.html)
        self.assertIn('id="asset-status"', self.html)
        self.assertIn('id="asset-status-text"', self.html)
        self.assertLess(
            self.html.index('id="model-status"'),
            self.html.index('id="asset-status"'),
        )
        self.assertIn('id="shutdown-button"', self.html)
        self.assertIn('id="app-sidebar"', self.html)
        self.assertIn('id="sidebar-toggle"', self.html)
        self.assertIn('class="brand-mark" aria-hidden="true">PA</span>', self.html)
        self.assertIn('id="workspace-label"', self.html)
        self.assertIn('id="current-context"', self.html)
        self.assertIn('id="table-splitter"', self.html)
        self.assertIn('id="document-splitter"', self.html)
        self.assertIn('role="separator"', self.html)
        self.assertNotIn('class="intro"', self.html)
        self.assertIn('role="tabpanel"', self.html)

    def test_table_form_requires_local_file_sheet_choice_and_question(self):
        self.assertIn('id="table-file"', self.html)
        self.assertIn('accept=".csv,.xlsx,.xlsm"', self.html)
        self.assertIn('id="select-table"', self.html)
        self.assertIn("Tabelle auswählen", self.html)
        self.assertIn('id="sheet-name"', self.html)
        self.assertIn('id="sheet-field"', self.html)
        self.assertIn('id="table-question"', self.html)
        self.assertIn('id="table-result-content"', self.html)
        self.assertNotIn('id="table-empty"', self.html)
        self.assertNotIn("Hier erscheint das lokal berechnete Ergebnis.", self.html)
        self.assertIn('id="select-table" class="button-primary table-picker"', self.html)
        self.assertIn('id="working-overlay"', self.html)
        self.assertNotIn('id="table-path"', self.html)
        self.assertIn('id="document-file"', self.html)
        self.assertIn('type="file"', self.html)
        self.assertIn('accept=".txt,.docx,.pdf"', self.html)
        self.assertIn('id="select-document"', self.html)
        self.assertIn("Datei auswählen und öffnen", self.html)
        self.assertNotIn('id="document-path"', self.html)

    def test_table_ui_uses_only_local_api_and_safe_dom_writes(self):
        self.assertIn('const TABLE_API = "/api/table"', self.javascript)
        self.assertIn('const TABLE_FILE_API = "/api/table-file"', self.javascript)
        self.assertIn(
            'const DOCUMENT_UPLOAD_API = "/api/document-upload"',
            self.javascript,
        )
        self.assertIn('const MEMORY_API = "/api/memory"', self.javascript)
        self.assertIn('const HEALTH_API = "/health"', self.javascript)
        self.assertIn('const SHUTDOWN_API = "/api/shutdown"', self.javascript)
        self.assertIn('operation: "shutdown"', self.javascript)
        self.assertIn("PortableAgent wirklich beenden?", self.javascript)
        self.assertIn(
            '"X-PortableAgent-Filename": encodeURIComponent(file.name)',
            self.javascript,
        )
        self.assertIn("pollModelUntilReady", self.javascript)
        self.assertIn("remainingAttempts = 30", self.javascript)
        self.assertIn(".shutdown-button", self.css)
        self.assertIn(".status{background:#080d0b;color:#f5faf7}", self.css)
        self.assertIn(".status.error{background:#7a2925;color:#fff}", self.css)
        self.assertIn("Lokales Modell nicht erreichbar", self.javascript)
        self.assertIn("KI-Dateien vorhanden", self.javascript)
        self.assertIn("Portable Runtime fehlt", self.javascript)
        self.assertIn("GGUF-Modell fehlt", self.javascript)
        self.assertIn(
            'elements.assetStatus.addEventListener("click"',
            self.javascript,
        )
        self.assertIn(".model-badge.checking", self.css)
        self.assertNotIn(".model-badge{font-size:0", self.css)
        self.assertIn('operation: "ask_table"', self.javascript)
        self.assertIn('operation: "list_sheets"', self.javascript)
        self.assertIn("renderSheetChoices", self.javascript)
        self.assertIn("isoDate[3]}.${isoDate[2]}.${isoDate[1]", self.javascript)
        self.assertIn("function formatDurationHours(value)", self.javascript)
        self.assertIn("function formatClockTime(value)", self.javascript)
        self.assertIn('semantics?.data_type === "duration"', self.javascript)
        self.assertIn('semantics?.data_type === "time"', self.javascript)
        self.assertIn('parts.join(" ")', self.javascript)
        self.assertIn("function beginWorking(messages)", self.javascript)
        self.assertIn("function endWorking()", self.javascript)
        self.assertIn("citation.row_values", self.javascript)
        self.assertIn("citation-row-fields", self.javascript)
        self.assertIn("details.open = openFirstRow && index === 0", self.javascript)
        self.assertIn("prefers-reduced-motion:reduce", self.css)
        self.assertIn("working-overlay", self.css)
        self.assertIn("sidebar-collapsed", self.css)
        self.assertIn("table-splitter", self.css)
        self.assertIn("function setWorkspaceSplit(", self.javascript)
        self.assertIn("configureWorkspaceSplitter(elements.documentMode", self.javascript)
        self.assertIn("const citedRows = result.citations.length", self.javascript)
        self.assertIn("setPointerCapture", self.javascript)
        self.assertIn("new TextEncoder()", self.javascript)
        self.assertIn('operation: "resolve_table"', self.javascript)
        self.assertIn("clarification-option", self.javascript)
        self.assertIn('result.clarification_kind === "entity"', self.javascript)
        self.assertIn("mögliche Aktion", self.javascript)
        self.assertIn("textContent", self.javascript)
        self.assertIn("createElement", self.javascript)
        self.assertNotIn("innerHTML", self.javascript)
        self.assertNotIn("outerHTML", self.javascript)
        self.assertNotIn("localStorage", self.javascript)
        self.assertNotIn("sessionStorage", self.javascript)
        self.assertNotIn("indexedDB", self.javascript)
        self.assertNotIn("https://", self.html + self.css + self.javascript)

    def test_memory_ui_requires_confirmation_and_has_no_automatic_import(self):
        self.assertIn('id="memory-text"', self.html)
        self.assertIn('maxlength="4000"', self.html)
        self.assertIn('id="memory-confirmation"', self.html)
        self.assertIn('id="memory-save-button"', self.html)
        self.assertIn('type="submit" disabled', self.html)
        self.assertIn("niemals automatisch übernommen", self.html)
        self.assertIn('operation: "list_notes"', self.javascript)
        self.assertIn('operation: "add_note"', self.javascript)
        self.assertIn('operation: "delete_note"', self.javascript)
        self.assertIn('confirmation: "confirmed"', self.javascript)
        self.assertIn("wirklich dauerhaft löschen?", self.javascript)
        self.assertIn(".memory-confirmation", self.css)
        self.assertIn(".memory-note", self.css)
        self.assertNotIn("documentApi({operation: \"add_note\"", self.javascript)

    def test_visible_ui_uses_informal_german_address(self):
        visible_sources = self.html + self.javascript
        self.assertIn("PortableAgent", visible_sources)
        self.assertIn("Keine Datei ausgewählt", visible_sources)
        self.assertIn("Deine Frage", visible_sources)
        self.assertIn("Du kannst diesen Tab jetzt schließen", visible_sources)
        self.assertIsNone(re.search(r"\b(?:Sie|Ihre|Ihnen|Ihr)\b", visible_sources))


if __name__ == "__main__":
    unittest.main()
