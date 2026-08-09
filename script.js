// script.js
// Zomato Notes frontend. Plain HTML/CSS/JS, no frameworks, no build step.

const API_BASE = "http://127.0.0.1:8000";
const DELETE_TOKEN = "super-secret-token"; // must match backend NOTES_DELETE_TOKEN

// Optional offline dev convenience (see mock-data.js). Grading uses false.
const USE_MOCK = false;

// ---------------------------------------------------------------------------
// Data layer: real fetch() calls against the live backend.
// ---------------------------------------------------------------------------

async function fetchNotes(tag) {
  if (USE_MOCK) return MOCK_NOTES;

  const url = tag ? `${API_BASE}/notes?tag=${encodeURIComponent(tag)}` : `${API_BASE}/notes`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch notes: ${response.status}`);
  }
  return response.json();
}

async function createNote(note) {
  if (USE_MOCK) {
    const fake = { ...note, id: Date.now(), ai_suggestion: null };
    MOCK_NOTES.push(fake);
    return fake;
  }

  const response = await fetch(`${API_BASE}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(note),
  });
  if (!response.ok) {
    throw new Error(`Failed to create note: ${response.status}`);
  }
  return response.json();
}

async function deleteNote(id) {
  if (USE_MOCK) return true;

  const response = await fetch(`${API_BASE}/notes/${id}`, {
    method: "DELETE",
    headers: { "x-token": DELETE_TOKEN },
  });
  if (!response.ok) {
    throw new Error(`Failed to delete note: ${response.status}`);
  }
  return true;
}

async function updateNoteTag(id, tag) {
  const response = await fetch(`${API_BASE}/notes/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tag }),
  });
  if (!response.ok) {
    throw new Error(`Failed to update note: ${response.status}`);
  }
  return response.json();
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let allNotes = [];

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

const notesListEl = document.getElementById("notes-list");
const loadingMessageEl = document.getElementById("loading-message");
const fetchErrorEl = document.getElementById("fetch-error");

function showFetchError(message) {
  fetchErrorEl.textContent = message;
  fetchErrorEl.hidden = false;
}

function clearFetchError() {
  fetchErrorEl.hidden = true;
  fetchErrorEl.textContent = "";
}

function buildNoteCard(note) {
  const card = document.createElement("article");
  card.className = "note-card";
  card.dataset.noteId = note.id;

  const title = document.createElement("h3");
  title.textContent = note.title;
  card.appendChild(title);

  if (note.tag) {
    const tagEl = document.createElement("span");
    tagEl.className = "note-tag";
    tagEl.textContent = note.tag;
    card.appendChild(tagEl);
  }

  const content = document.createElement("p");
  content.textContent = note.content;
  card.appendChild(content);

  if (note.ai_suggestion) {
    card.appendChild(buildAiPanel(note));
  }

  const actions = document.createElement("div");
  actions.className = "note-actions";

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.textContent = "Delete";
  deleteBtn.addEventListener("click", async () => {
    try {
      await deleteNote(note.id);
      card.remove();
    } catch (err) {
      showFetchError(`Could not delete note: ${err.message}`);
    }
  });
  actions.appendChild(deleteBtn);
  card.appendChild(actions);

  return card;
}

function buildAiPanel(note) {
  const panel = document.createElement("div");
  panel.className = "ai-panel";

  const label = document.createElement("strong");
  label.textContent = "AI Suggests: ";
  panel.appendChild(label);

  const tagsSpan = document.createElement("span");
  tagsSpan.textContent = `tags: ${note.ai_suggestion.tags.join(", ")}`;
  panel.appendChild(tagsSpan);

  const summary = document.createElement("p");
  summary.textContent = note.ai_suggestion.summary;
  panel.appendChild(summary);

  const applyBtn = document.createElement("button");
  applyBtn.type = "button";
  applyBtn.textContent = "Apply as tag";
  applyBtn.addEventListener("click", async () => {
    const firstTag = note.ai_suggestion.tags[0];
    try {
      await updateNoteTag(note.id, firstTag);
      const tagEl = panel.closest(".note-card").querySelector(".note-tag");
      if (tagEl) tagEl.textContent = firstTag;
    } catch (err) {
      showFetchError(`Could not apply tag: ${err.message}`);
    }
  });
  panel.appendChild(applyBtn);

  return panel;
}

function renderNotes(notes) {
  notesListEl.innerHTML = "";
  notes.forEach((note) => {
    notesListEl.appendChild(buildNoteCard(note));
  });
}

async function loadNotes() {
  loadingMessageEl.hidden = false;
  clearFetchError();
  try {
    allNotes = await fetchNotes();
    renderNotes(allNotes);
  } catch (err) {
    showFetchError(`Could not load notes: ${err.message}`);
  } finally {
    loadingMessageEl.hidden = true;
  }
}

// ---------------------------------------------------------------------------
// Add note form: validation + submit
// ---------------------------------------------------------------------------

const addNoteForm = document.getElementById("add-note-form");
const formErrorEl = document.getElementById("form-error");

function showFormError(message) {
  formErrorEl.textContent = message;
  formErrorEl.hidden = false;
}

function clearFormError() {
  formErrorEl.hidden = true;
  formErrorEl.textContent = "";
}

addNoteForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFormError();

  const titleInput = document.getElementById("note-title");
  const contentInput = document.getElementById("note-content");
  const tagInput = document.getElementById("note-tag");

  const title = titleInput.value.trim();
  const content = contentInput.value.trim();
  const tag = tagInput.value.trim();

  if (!title || !content) {
    showFormError("Title and content are required.");
    return;
  }

  try {
    const created = await createNote({ title, content, tag: tag || null, owner_id: 1 });
    allNotes.push(created);
    notesListEl.appendChild(buildNoteCard(created));
    addNoteForm.reset();
  } catch (err) {
    showFormError(`Could not add note: ${err.message}`);
  }
});

// ---------------------------------------------------------------------------
// Debounced plain-text search (client-side filter over already-fetched notes)
// ---------------------------------------------------------------------------

const plainSearchInput = document.getElementById("plain-search");
let debounceTimer = null;

plainSearchInput.addEventListener("input", () => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    const query = plainSearchInput.value.trim().toLowerCase();
    if (!query) {
      renderNotes(allNotes);
      return;
    }
    const filtered = allNotes.filter(
      (n) =>
        n.title.toLowerCase().includes(query) ||
        (n.tag && n.tag.toLowerCase().includes(query))
    );
    renderNotes(filtered);
  }, 400);
});

// ---------------------------------------------------------------------------
// Part 2: Sort by (Relevance / Date) — wired to GET /notes/search
// ---------------------------------------------------------------------------

const sortBySelect = document.getElementById("sort-by-select");

sortBySelect.addEventListener("change", async () => {
  const mode = sortBySelect.value;
  const keyword = plainSearchInput.value.trim();

  try {
    let url;
    if (mode === "date") {
      url = `${API_BASE}/notes/search?sort_by=date`;
    } else {
      if (!keyword) return; // relevance mode needs a keyword
      url = `${API_BASE}/notes/search?keyword=${encodeURIComponent(keyword)}`;
    }
    const response = await fetch(url);
    if (!response.ok) throw new Error(`status ${response.status}`);
    const results = await response.json();
    renderNotes(results);
  } catch (err) {
    showFetchError(`Sort request failed: ${err.message}`);
  }
});

// ---------------------------------------------------------------------------
// Part 2: Jump to exact title — wired to GET /notes/lookup
// ---------------------------------------------------------------------------

const jumpTitleInput = document.getElementById("jump-title");
const jumpAlgoSelect = document.getElementById("jump-algo");
const jumpBtn = document.getElementById("jump-btn");
const lookupResultEl = document.getElementById("lookup-result");

jumpBtn.addEventListener("click", async () => {
  const title = jumpTitleInput.value.trim();
  if (!title) return;
  const algo = jumpAlgoSelect.value;

  try {
    const url = `${API_BASE}/notes/lookup?title=${encodeURIComponent(title)}&algo=${algo}`;
    const response = await fetch(url);
    const data = await response.json();

    lookupResultEl.innerHTML = "";
    if (!data.found) {
      const msg = document.createElement("p");
      msg.textContent = `No exact match for "${title}".`;
      lookupResultEl.appendChild(msg);
      return;
    }
    renderNotes(allNotes); // reset list, then highlight the match
    const card = notesListEl.querySelector(`[data-note-id="${data.note.id}"]`);
    if (card) {
      card.classList.add("highlight");
      card.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  } catch (err) {
    showFetchError(`Lookup failed: ${err.message}`);
  }
});

// ---------------------------------------------------------------------------
// Part 2: Quick tag jump — wired to GET /notes/quick-find
// ---------------------------------------------------------------------------

const QUICK_TAGS = ["work", "health", "recipes", "travel", "random"];
const quickTagButtonsEl = document.getElementById("quick-tag-buttons");

QUICK_TAGS.forEach((tag) => {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = tag;
  btn.addEventListener("click", async () => {
    try {
      const response = await fetch(`${API_BASE}/notes/quick-find?tag=${encodeURIComponent(tag)}`);
      const data = await response.json();

      lookupResultEl.innerHTML = "";
      if (!data.found) {
        const msg = document.createElement("p");
        msg.textContent = `No note found with tag "${tag}".`;
        lookupResultEl.appendChild(msg);
        return;
      }
      renderNotes(allNotes);
      const card = notesListEl.querySelector(`[data-note-id="${data.note.id}"]`);
      if (card) {
        card.classList.add("highlight");
        card.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    } catch (err) {
      showFetchError(`Quick tag jump failed: ${err.message}`);
    }
  });
  quickTagButtonsEl.appendChild(btn);
});

// ---------------------------------------------------------------------------
// Part 3: Smart Search (AI) — wired to GET /notes/smart-search
// ---------------------------------------------------------------------------

const smartSearchInput = document.getElementById("smart-search-input");
const smartSearchBtn = document.getElementById("smart-search-btn");
const smartSearchResultEl = document.getElementById("smart-search-result");

smartSearchBtn.addEventListener("click", async () => {
  const query = smartSearchInput.value.trim();
  if (!query) return;

  try {
    const response = await fetch(`${API_BASE}/notes/smart-search?q=${encodeURIComponent(query)}`);
    if (!response.ok) throw new Error(`status ${response.status}`);
    const results = await response.json();

    smartSearchResultEl.innerHTML = "";
    const heading = document.createElement("h4");
    heading.textContent = `Smart Search results for "${query}"`;
    smartSearchResultEl.appendChild(heading);

    results.forEach((note) => {
      const card = document.createElement("div");
      card.className = "note-card";

      const title = document.createElement("h3");
      title.textContent = note.title;
      card.appendChild(title);

      const content = document.createElement("p");
      content.textContent = note.content;
      card.appendChild(content);

      const score = document.createElement("span");
      score.className = "similarity-score";
      score.textContent = `similarity: ${note.similarity}`;
      card.appendChild(score);

      smartSearchResultEl.appendChild(card);
    });
  } catch (err) {
    showFetchError(`Smart search failed: ${err.message}`);
  }
});

// ---------------------------------------------------------------------------
// Recursive nested-tag category tree
// ---------------------------------------------------------------------------

const CATEGORY_TREE = {
  name: "All Tags",
  children: [
    {
      name: "Work",
      children: [
        { name: "Standups", children: [] },
        { name: "Retros", children: [] },
      ],
    },
    {
      name: "Personal",
      children: [
        { name: "Health", children: [{ name: "Fitness", children: [] }] },
        { name: "Recipes", children: [] },
      ],
    },
    { name: "Travel", children: [] },
  ],
};

function renderCategoryNode(node) {
  const li = document.createElement("li");

  if (node.children && node.children.length > 0) {
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "tree-toggle";
    toggle.textContent = `▸ ${node.name}`;

    const childList = document.createElement("ul");
    childList.classList.add("collapsed");

    node.children.forEach((child) => {
      childList.appendChild(renderCategoryNode(child));
    });

    toggle.addEventListener("click", () => {
      childList.classList.toggle("collapsed");
      toggle.textContent = childList.classList.contains("collapsed")
        ? `▸ ${node.name}`
        : `▾ ${node.name}`;
    });

    li.appendChild(toggle);
    li.appendChild(childList);
  } else {
    const span = document.createElement("span");
    span.textContent = node.name;
    li.appendChild(span);
  }

  return li;
}

function renderCategoryTree(root, container) {
  const rootList = document.createElement("ul");
  rootList.appendChild(renderCategoryNode(root));
  container.appendChild(rootList);
}

renderCategoryTree(CATEGORY_TREE, document.getElementById("category-tree"));

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

loadNotes();
