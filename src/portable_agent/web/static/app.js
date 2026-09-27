"use strict";

const DOCUMENT_API = "/api/document";
const DOCUMENT_UPLOAD_API = "/api/document-upload";
const TABLE_API = "/api/table";
const TABLE_FILE_API = "/api/table-file";
const MEMORY_API = "/api/memory";
const HEALTH_API = "/health";
const SHUTDOWN_API = "/api/shutdown";

const elements = {
  documentTab: document.querySelector("#document-tab"),
  tableTab: document.querySelector("#table-tab"),
  memoryTab: document.querySelector("#memory-tab"),
  documentMode: document.querySelector("#document-mode"),
  tableMode: document.querySelector("#table-mode"),
  memoryMode: document.querySelector("#memory-mode"),
  assetStatus: document.querySelector("#asset-status"),
  assetStatusText: document.querySelector("#asset-status-text"),
  modelStatus: document.querySelector("#model-status"),
  modelStatusText: document.querySelector("#model-status-text"),
  shutdown: document.querySelector("#shutdown-button"),
  importForm: document.querySelector("#import-form"),
  documentFile: document.querySelector("#document-file"),
  selectDocument: document.querySelector("#select-document"),
  sessionSelect: document.querySelector("#session-select"),
  refresh: document.querySelector("#refresh-sessions"),
  release: document.querySelector("#release-session"),
  releaseAll: document.querySelector("#release-all"),
  questionForm: document.querySelector("#question-form"),
  question: document.querySelector("#question"),
  ask: document.querySelector("#ask-button"),
  empty: document.querySelector("#answer-empty"),
  card: document.querySelector("#answer-card"),
  answer: document.querySelector("#answer-text"),
  matchCount: document.querySelector("#match-count"),
  citations: document.querySelector("#citations"),
  tableForm: document.querySelector("#table-form"),
  tableFile: document.querySelector("#table-file"),
  selectTable: document.querySelector("#select-table"),
  selectedTableName: document.querySelector("#selected-table-name"),
  sheetField: document.querySelector("#sheet-field"),
  sheetName: document.querySelector("#sheet-name"),
  tableQuestion: document.querySelector("#table-question"),
  tableAsk: document.querySelector("#table-ask-button"),
  tableEmpty: document.querySelector("#table-empty"),
  tableCard: document.querySelector("#table-result-card"),
  tableContent: document.querySelector("#table-result-content"),
  tableCitationHeading: document.querySelector("#table-citation-title").parentElement,
  tableMatchCount: document.querySelector("#table-match-count"),
  tableCitations: document.querySelector("#table-citations"),
  memoryForm: document.querySelector("#memory-form"),
  memoryText: document.querySelector("#memory-text"),
  memoryConfirmation: document.querySelector("#memory-confirmation"),
  memorySave: document.querySelector("#memory-save-button"),
  memoryRefresh: document.querySelector("#refresh-memory"),
  memoryEmpty: document.querySelector("#memory-empty"),
  memoryList: document.querySelector("#memory-list"),
  status: document.querySelector("#status"),
};

let statusTimer;
let startupPollTimer;
let shuttingDown = false;
let selectedTableFile = null;

async function api(endpoint, payload) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {"Content-Type": "application/json; charset=utf-8"},
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok || !result.ok) {
    throw new Error(result?.error?.message || "Lokale Anfrage fehlgeschlagen.");
  }
  return result;
}

function documentApi(payload) {
  return api(DOCUMENT_API, payload);
}

async function uploadDocument(file) {
  const response = await fetch(DOCUMENT_UPLOAD_API, {
    method: "POST",
    headers: {
      "Content-Type": "application/octet-stream",
      "X-PortableAgent-Filename": encodeURIComponent(file.name),
    },
    body: file,
  });
  const result = await response.json();
  if (!response.ok || !result.ok) {
    throw new Error(result?.error?.message || "Die lokale Datei konnte nicht geöffnet werden.");
  }
  return result;
}

function tableApi(payload) {
  return api(TABLE_API, payload);
}

async function tableFileApi(file, metadata) {
  const metadataBytes = new TextEncoder().encode(JSON.stringify(metadata));
  const prefix = new Uint8Array(4);
  new DataView(prefix.buffer).setUint32(0, metadataBytes.byteLength, false);
  const envelope = new Blob(
    [prefix, metadataBytes, file],
    {type: "application/vnd.portable-agent.table"},
  );
  const response = await fetch(TABLE_FILE_API, {
    method: "POST",
    headers: {"Content-Type": "application/vnd.portable-agent.table"},
    body: envelope,
  });
  const result = await response.json();
  if (!response.ok || !result.ok) {
    throw new Error(result?.error?.message || "Die lokale Tabelle konnte nicht verarbeitet werden.");
  }
  return result;
}

function memoryApi(payload) {
  return api(MEMORY_API, payload);
}

async function refreshModelStatus() {
  let ready = false;
  elements.assetStatus.classList.remove("ready", "unavailable");
  elements.assetStatus.classList.add("checking");
  elements.assetStatusText.textContent = "KI-Dateien werden geprüft";
  elements.modelStatus.classList.remove("ready", "unavailable");
  elements.modelStatus.classList.add("checking");
  elements.modelStatusText.textContent = "Modell wird geprüft";
  try {
    const response = await fetch(HEALTH_API, {cache: "no-store"});
    const health = await response.json();
    ready = response.ok && health?.model?.status === "ready";
    const assetsReady = response.ok && health?.assets?.status === "ready";
    const runtimeAvailable = assetsReady && health.assets.llama_runtime?.available === true;
    const modelAvailable = assetsReady && health.assets.gguf_models?.available === true;
    const allAssetsAvailable = runtimeAvailable && modelAvailable;
    elements.assetStatus.classList.toggle("ready", allAssetsAvailable);
    elements.assetStatus.classList.toggle("unavailable", !allAssetsAvailable);
    if (!assetsReady) {
      elements.assetStatusText.textContent = "Dateistatus nicht verfügbar";
    } else if (allAssetsAvailable) {
      elements.assetStatusText.textContent = "Runtime und GGUF-Modell vorhanden";
    } else if (!runtimeAvailable && !modelAvailable) {
      elements.assetStatusText.textContent = "Runtime und GGUF-Modell fehlen";
    } else if (!runtimeAvailable) {
      elements.assetStatusText.textContent = "Portable Runtime fehlt";
    } else {
      elements.assetStatusText.textContent = "GGUF-Modell fehlt";
    }
    elements.modelStatus.classList.toggle("ready", ready);
    elements.modelStatus.classList.toggle("unavailable", !ready);
    elements.modelStatusText.textContent = ready
      ? "Lokales Modell bereit"
      : "Lokales Modell nicht erreichbar";
  } catch (_) {
    elements.assetStatus.classList.add("unavailable");
    elements.assetStatusText.textContent = "Dateistatus nicht verfügbar";
    elements.modelStatus.classList.add("unavailable");
    elements.modelStatusText.textContent = "Lokales Modell nicht erreichbar";
  } finally {
    elements.assetStatus.classList.remove("checking");
    elements.modelStatus.classList.remove("checking");
  }
  return ready;
}

async function pollModelUntilReady(remainingAttempts = 30) {
  const ready = await refreshModelStatus();
  if (!ready && !shuttingDown && remainingAttempts > 1) {
    startupPollTimer = setTimeout(
      () => pollModelUntilReady(remainingAttempts - 1),
      2000,
    );
  }
}

function showStatus(message, error = false) {
  clearTimeout(statusTimer);
  elements.status.textContent = message;
  elements.status.classList.toggle("error", error);
  elements.status.classList.add("visible");
  statusTimer = setTimeout(() => elements.status.classList.remove("visible"), 4200);
}

function setBusy(button, busy, label) {
  if (!button.dataset.label) button.dataset.label = button.textContent;
  button.disabled = busy;
  button.textContent = busy ? label : button.dataset.label;
}

function setMode(mode) {
  const modes = [
    ["document", elements.documentTab, elements.documentMode],
    ["table", elements.tableTab, elements.tableMode],
    ["memory", elements.memoryTab, elements.memoryMode],
  ];
  for (const [name, tab, panel] of modes) {
    const active = name === mode;
    panel.hidden = !active;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  }
}

function updateMemorySaveState() {
  elements.memorySave.disabled = !elements.memoryConfirmation.checked
    || !elements.memoryText.value.trim();
}

function renderMemoryNotes(notes) {
  elements.memoryList.replaceChildren();
  elements.memoryEmpty.hidden = notes.length > 0;
  elements.memoryList.hidden = notes.length === 0;
  for (const note of notes) {
    const item = document.createElement("li");
    item.className = "memory-note";
    const content = document.createElement("div");
    const text = document.createElement("p");
    text.textContent = note.text;
    const created = document.createElement("small");
    created.textContent = `Lokal gespeichert: ${note.created_at}`;
    content.append(text, created);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "button-danger memory-delete";
    remove.textContent = "Löschen";
    remove.addEventListener("click", () => deleteMemoryNote(note.id, remove));
    item.append(content, remove);
    elements.memoryList.append(item);
  }
}

async function refreshMemoryNotes() {
  const result = await memoryApi({operation: "list_notes"});
  renderMemoryNotes(result.notes);
}

async function deleteMemoryNote(noteId, button) {
  if (!window.confirm("Diese Wissensnotiz wirklich dauerhaft löschen?")) return;
  setBusy(button, true, "Wird gelöscht …");
  try {
    await memoryApi({
      operation: "delete_note",
      note_id: noteId,
      confirmation: "confirmed",
    });
    await refreshMemoryNotes();
    showStatus("Wissensnotiz wurde dauerhaft gelöscht.");
  } catch (error) {
    setBusy(button, false, "");
    showStatus(error.message, true);
  }
}

function updateControls() {
  const selected = Boolean(elements.sessionSelect.value);
  const hasSessions = elements.sessionSelect.options.length > 1;
  elements.release.disabled = !selected;
  elements.releaseAll.disabled = !hasSessions;
  elements.question.disabled = !selected;
  elements.ask.disabled = !selected;
}

async function refreshSessions(preferredId = "") {
  const result = await documentApi({operation: "list_sessions"});
  const previous = preferredId || elements.sessionSelect.value;
  elements.sessionSelect.replaceChildren();
  const emptyOption = document.createElement("option");
  emptyOption.value = "";
  emptyOption.textContent = result.sessions.length ? "Dokument auswählen" : "Noch kein Dokument geöffnet";
  elements.sessionSelect.append(emptyOption);
  for (const session of result.sessions) {
    const option = document.createElement("option");
    option.value = session.session_id;
    option.textContent = session.display_name;
    elements.sessionSelect.append(option);
  }
  if (result.sessions.some((session) => session.session_id === previous)) {
    elements.sessionSelect.value = previous;
  }
  updateControls();
}

function clearAnswer() {
  elements.card.hidden = true;
  elements.empty.hidden = false;
  elements.answer.textContent = "";
  elements.citations.replaceChildren();
}

function clearTableResult() {
  elements.tableCard.hidden = true;
  elements.tableEmpty.hidden = false;
  elements.tableContent.replaceChildren();
  elements.tableCitations.replaceChildren();
}

function updateTableAskState() {
  const sheetReady = elements.sheetField.hidden || Boolean(elements.sheetName.value);
  elements.tableAsk.disabled = !selectedTableFile
    || !elements.tableQuestion.value.trim()
    || !sheetReady;
}

function renderSheetChoices(sheetNames) {
  elements.sheetName.replaceChildren();
  if (sheetNames.length > 1) {
    const prompt = document.createElement("option");
    prompt.value = "";
    prompt.textContent = "Tabellenblatt auswählen";
    elements.sheetName.append(prompt);
  }
  for (const sheetName of sheetNames) {
    const option = document.createElement("option");
    option.value = sheetName;
    option.textContent = sheetName;
    elements.sheetName.append(option);
  }
  elements.sheetName.disabled = false;
  if (sheetNames.length === 1) elements.sheetName.value = sheetNames[0];
}

function citationLocation(citation) {
  const parts = [];
  if (citation.section) parts.push(citation.section);
  if (citation.page) parts.push(`Seite ${citation.page}`);
  if (citation.paragraph) parts.push(citation.paragraph);
  if (citation.row) parts.push(`Zeile ${citation.row}`);
  return parts.join(" · ") || "Quellenfundstelle";
}

function renderCitations(citations, target) {
  target.replaceChildren();
  for (const citation of citations) {
    const item = document.createElement("li");
    item.className = "citation";
    const source = document.createElement("strong");
    source.textContent = citation.display_name;
    const location = document.createElement("small");
    location.textContent = citationLocation(citation);
    item.append(source, location);
    if (citation.excerpt) {
      const excerpt = document.createElement("blockquote");
      excerpt.textContent = citation.excerpt;
      item.append(excerpt);
    }
    target.append(item);
  }
}

function renderAnswer(answer) {
  elements.answer.textContent = answer.text;
  elements.matchCount.textContent = `${answer.matched_chunks} Fundstelle${answer.matched_chunks === 1 ? "" : "n"}`;
  renderCitations(answer.citations, elements.citations);
  elements.empty.hidden = true;
  elements.card.hidden = false;
}

function displayValue(value) {
  if (value === null || value === undefined) return "–";
  if (typeof value === "boolean") return value ? "Ja" : "Nein";
  if (typeof value === "object") return JSON.stringify(value);
  if (typeof value === "string") {
    const isoDate = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (isoDate) return `${isoDate[3]}.${isoDate[2]}.${isoDate[1]}`;
  }
  return String(value);
}

function renderValueList(values) {
  const list = document.createElement("dl");
  list.className = "result-values";
  for (const [label, value] of Object.entries(values)) {
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = displayValue(value);
    list.append(term, description);
  }
  elements.tableContent.append(list);
}

function renderGroupTable(groups) {
  const headers = [];
  for (const group of groups) {
    for (const key of Object.keys(group)) {
      if (!headers.includes(key)) headers.push(key);
    }
  }
  const wrapper = document.createElement("div");
  wrapper.className = "group-table-wrap";
  const table = document.createElement("table");
  table.className = "group-table";
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const header of headers) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = header;
    headRow.append(cell);
  }
  head.append(headRow);
  const body = document.createElement("tbody");
  for (const group of groups) {
    const row = document.createElement("tr");
    for (const header of headers) {
      const cell = document.createElement("td");
      cell.textContent = displayValue(group[header]);
      row.append(cell);
    }
    body.append(row);
  }
  table.append(head, body);
  wrapper.append(table);
  elements.tableContent.append(wrapper);
}

function renderClarification(result) {
  const box = document.createElement("div");
  box.className = "clarification";
  const title = document.createElement("h3");
  title.textContent = result.question;
  const note = document.createElement("p");
  note.textContent = `${result.matched_rows} passende Zeilen. Präzisiere deine Frage mit einer der folgenden Berechnungen:`;
  const options = document.createElement("div");
  options.className = "clarification-options";
  for (const option of result.options) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "clarification-option";
    button.textContent = option.label;
    button.addEventListener("click", () => resolveClarification(
      result.clarification_id,
      option.id,
    ));
    options.append(button);
  }
  box.append(title, note, options);
  elements.tableContent.append(box);
  elements.tableMatchCount.textContent = `${result.matched_rows} passende Zeilen`;
  elements.tableCitationHeading.hidden = true;
}

async function resolveClarification(clarificationId, optionId) {
  const buttons = elements.tableContent.querySelectorAll(".clarification-option");
  for (const button of buttons) button.disabled = true;
  try {
    const response = await tableApi({
      operation: "resolve_table",
      clarification_id: clarificationId,
      option_id: optionId,
    });
    renderTableResult(response.result);
    showStatus("Rückfrage lokal aufgelöst. Kein weiterer Modellaufruf.");
  } catch (error) {
    for (const button of buttons) button.disabled = false;
    showStatus(error.message, true);
  }
}

function renderTableResult(result) {
  elements.tableContent.replaceChildren();
  elements.tableCitations.replaceChildren();
  elements.tableCitationHeading.hidden = false;
  if (result.type === "clarification") {
    renderClarification(result);
  } else {
    const groups = result.values?.groups;
    if (Array.isArray(groups)) renderGroupTable(groups);
    else renderValueList(result.values || {});
    const matchedRows = result.metadata?.matched_rows ?? result.citations.length;
    elements.tableMatchCount.textContent = `${matchedRows} verwendete Zeile${matchedRows === 1 ? "" : "n"}`;
    renderCitations(result.citations, elements.tableCitations);
  }
  elements.tableEmpty.hidden = true;
  elements.tableCard.hidden = false;
}

elements.documentTab.addEventListener("click", () => setMode("document"));
elements.tableTab.addEventListener("click", () => setMode("table"));
elements.memoryTab.addEventListener("click", () => setMode("memory"));
elements.assetStatus.addEventListener("click", () => refreshModelStatus());
elements.modelStatus.addEventListener("click", () => refreshModelStatus());
elements.shutdown.addEventListener("click", async () => {
  if (!window.confirm("PortableAgent wirklich beenden? Offene temporäre Sitzungen werden freigegeben.")) return;
  shuttingDown = true;
  clearTimeout(startupPollTimer);
  setBusy(elements.shutdown, true, "Wird beendet …");
  try {
    await api(SHUTDOWN_API, {operation: "shutdown"});
    clearTimeout(statusTimer);
    elements.status.textContent = "PortableAgent wurde beendet. Du kannst diesen Tab jetzt schließen.";
    elements.status.classList.remove("error");
    elements.status.classList.add("visible");
    elements.shutdown.textContent = "Beendet";
  } catch (error) {
    setBusy(elements.shutdown, false, "");
    showStatus(error.message, true);
  }
});
const modeTabs = [elements.documentTab, elements.tableTab, elements.memoryTab];
for (const [index, tab] of modeTabs.entries()) {
  tab.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const direction = event.key === "ArrowRight" ? 1 : -1;
    const next = modeTabs[(index + direction + modeTabs.length) % modeTabs.length];
    const nextMode = next === elements.documentTab
      ? "document"
      : next === elements.tableTab ? "table" : "memory";
    setMode(nextMode);
    next.focus();
  });
}

elements.selectDocument.addEventListener("click", () => {
  elements.documentFile.value = "";
  elements.documentFile.click();
});

elements.documentFile.addEventListener("change", async () => {
  const [file] = elements.documentFile.files;
  if (!file) return;
  setBusy(elements.selectDocument, true, "Wird lokal geöffnet …");
  try {
    const result = await uploadDocument(file);
    await refreshSessions(result.session.session_id);
    clearAnswer();
    showStatus(`${result.session.display_name} wurde lokal geöffnet.`);
    elements.question.focus();
  } catch (error) {
    showStatus(error.message, true);
  } finally {
    elements.documentFile.value = "";
    setBusy(elements.selectDocument, false, "");
  }
});

elements.questionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setBusy(elements.ask, true, "Lokale Analyse …");
  try {
    const result = await documentApi({
      operation: "ask",
      session_id: elements.sessionSelect.value,
      question: elements.question.value,
    });
    renderAnswer(result.answer);
    showStatus("Antwort mit lokalen Fundstellen erstellt.");
  } catch (error) {
    showStatus(error.message, true);
  } finally {
    setBusy(elements.ask, false, "");
    updateControls();
  }
});

elements.selectTable.addEventListener("click", () => {
  elements.tableFile.value = "";
  elements.tableFile.click();
});

elements.tableFile.addEventListener("change", async () => {
  const [file] = elements.tableFile.files;
  if (!file) return;
  if (file.size > 100 * 1024 * 1024) {
    showStatus("Die Tabelle ist größer als das erlaubte Limit von 100 MiB.", true);
    return;
  }
  selectedTableFile = null;
  elements.sheetField.hidden = true;
  elements.sheetName.disabled = true;
  elements.selectedTableName.classList.remove("ready");
  elements.selectedTableName.textContent = "Tabelle wird lokal geprüft …";
  updateTableAskState();
  clearTableResult();
  setBusy(elements.selectTable, true, "Tabelle wird geprüft …");
  try {
    const result = await tableFileApi(file, {
      operation: "list_sheets",
      filename: file.name,
    });
    selectedTableFile = file;
    elements.selectedTableName.textContent = file.name;
    elements.selectedTableName.classList.add("ready");
    if (result.file_type === "excel") {
      renderSheetChoices(result.sheet_names);
      elements.sheetField.hidden = false;
      const sheetLabel = result.sheet_names.length === 1
        ? "Tabellenblatt gefunden."
        : "Tabellenblätter gefunden.";
      showStatus(`${result.sheet_names.length} ${sheetLabel}`);
    } else {
      elements.sheetName.replaceChildren();
      elements.sheetName.disabled = true;
      elements.sheetField.hidden = true;
      showStatus(`${file.name} wurde lokal ausgewählt.`);
    }
    elements.selectTable.dataset.label = "Andere Tabelle auswählen";
  } catch (error) {
    elements.selectedTableName.textContent = "Noch keine Tabelle ausgewählt";
    showStatus(error.message, true);
  } finally {
    elements.tableFile.value = "";
    setBusy(elements.selectTable, false, "");
    updateTableAskState();
  }
});

elements.sheetName.addEventListener("change", updateTableAskState);
elements.tableQuestion.addEventListener("input", updateTableAskState);

elements.tableForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedTableFile) {
    showStatus("Bitte wähle zuerst eine Tabelle aus.", true);
    return;
  }
  setBusy(elements.tableAsk, true, "Lokale Berechnung …");
  const metadata = {
    operation: "ask_table",
    filename: selectedTableFile.name,
    question: elements.tableQuestion.value,
  };
  if (!elements.sheetField.hidden) metadata.sheet_name = elements.sheetName.value;
  try {
    const response = await tableFileApi(selectedTableFile, metadata);
    renderTableResult(response.result);
    const message = response.result.type === "clarification"
      ? "Eine Präzisierung ist erforderlich."
      : "Tabellenergebnis mit lokalen Zeilenbelegen erstellt.";
    showStatus(message);
  } catch (error) {
    clearTableResult();
    showStatus(error.message, true);
  } finally {
    setBusy(elements.tableAsk, false, "");
    updateTableAskState();
  }
});

elements.refresh.addEventListener("click", () => refreshSessions().catch((error) => showStatus(error.message, true)));
elements.sessionSelect.addEventListener("change", () => { clearAnswer(); updateControls(); });
elements.release.addEventListener("click", async () => {
  try {
    await documentApi({operation: "release", session_id: elements.sessionSelect.value});
    await refreshSessions();
    clearAnswer();
    showStatus("Dokumentsitzung wurde freigegeben.");
  } catch (error) { showStatus(error.message, true); }
});
elements.releaseAll.addEventListener("click", async () => {
  try {
    const result = await documentApi({operation: "release_all"});
    await refreshSessions();
    clearAnswer();
    showStatus(`${result.released_count} Sitzung(en) wurden freigegeben.`);
  } catch (error) { showStatus(error.message, true); }
});

elements.memoryText.addEventListener("input", updateMemorySaveState);
elements.memoryConfirmation.addEventListener("change", updateMemorySaveState);
elements.memoryRefresh.addEventListener("click", () => refreshMemoryNotes().catch((error) => showStatus(error.message, true)));
elements.memoryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!elements.memoryConfirmation.checked) {
    showStatus("Bitte bestätige die dauerhafte lokale Speicherung.", true);
    return;
  }
  setBusy(elements.memorySave, true, "Wird gespeichert …");
  try {
    await memoryApi({
      operation: "add_note",
      text: elements.memoryText.value,
      confirmation: "confirmed",
    });
    elements.memoryText.value = "";
    elements.memoryConfirmation.checked = false;
    await refreshMemoryNotes();
    showStatus("Wissensnotiz wurde bestätigt lokal gespeichert.");
  } catch (error) {
    showStatus(error.message, true);
  } finally {
    setBusy(elements.memorySave, false, "");
    updateMemorySaveState();
  }
});

setMode("document");
pollModelUntilReady();
refreshSessions().catch((error) => showStatus(error.message, true));
refreshMemoryNotes().catch((error) => showStatus(error.message, true));
