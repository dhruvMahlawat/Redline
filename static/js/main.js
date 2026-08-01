const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const status = document.getElementById("status");
const results = document.getElementById("results");

let isProcessing = false;

// click the drop zone opens the file picker, same as any normal upload
dropZone.addEventListener("click", () => {
    if (!isProcessing) fileInput.click();
});

dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    if (!isProcessing) dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (isProcessing) return;
    if (e.dataTransfer.files.length) {
        handleFile(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener("change", () => {
    if (isProcessing) return;
    if (fileInput.files.length) {
        handleFile(fileInput.files[0]);
    }
});

function setStatus(text, showSpinner = false) {
    status.innerHTML = "";
    if (showSpinner) {
        const spinner = document.createElement("span");
        spinner.className = "spinner";
        status.appendChild(spinner);
    }
    status.appendChild(document.createTextNode(text));
}

async function handleFile(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
        status.textContent = "Please upload a PDF.";
        return;
    }

    isProcessing = true;
    dropZone.classList.add("busy");
    setStatus("Reading your lease...", true);
    results.hidden = true;

    const formData = new FormData();
    formData.append("file", file);

    try {
        const res = await fetch("/analyze", { method: "POST", body: formData });
        const data = await res.json();

        if (!res.ok) {
            setStatus(data.error || "Something went wrong.");
            return;
        }

        setStatus(`Analyzed ${data.clause_count} clauses.`);
        renderResults(data.facts, data.red_flags, data.page_images);
    } catch (err) {
        setStatus("Couldn't reach the server.");
    } finally {
        isProcessing = false;
        dropZone.classList.remove("busy");
        fileInput.value = "";  // so re-selecting the same file still fires 'change'
    }
}

function renderResults(facts, redFlags, pageImages) {
    results.innerHTML = "";

    if (facts.length) {
        const heading = document.createElement("h2");
        heading.textContent = "Key facts";
        results.appendChild(heading);
        facts.forEach((f) => results.appendChild(buildCard(f.field.replace(/_/g, " "), f.value, f, pageImages)));
    }

    if (redFlags.length) {
        const heading = document.createElement("h2");
        heading.textContent = "Worth a second look";
        results.appendChild(heading);
        redFlags.forEach((f) => results.appendChild(buildCard(f.severity + " severity", f.description, f, pageImages)));
    }

    results.hidden = false;
}

const CONFIDENCE_WARNINGS = {
    medium: "⚠ quote doesn't clearly support this",
    low: "⚠ quote not found in document",
};

function buildCard(title, body, item, pageImages) {
    const { confidence, page, source_quote, reasoning } = item;
    const card = document.createElement("div");
    card.className = "clause-card" + (confidence !== "high" ? " flagged" : "");

    const titleEl = document.createElement("h3");
    titleEl.textContent = title;

    const text = document.createElement("p");
    text.textContent = body;

    card.appendChild(titleEl);
    card.appendChild(text);

    if (source_quote) {
        const quote = document.createElement("blockquote");
        quote.className = "source-quote";
        quote.textContent = source_quote;
        card.appendChild(quote);
    }

    const imageData = pageImages && pageImages[page];

    if (page) {
        const pageTag = document.createElement("span");
        pageTag.className = "badge page-badge";
        pageTag.textContent = imageData ? `page ${page} - click to view` : `page ${page}`;
        if (imageData) {
            pageTag.style.cursor = "pointer";
            pageTag.addEventListener("click", () => togglePageImage(card, imageData));
        }
        card.appendChild(pageTag);
    }

    if (CONFIDENCE_WARNINGS[confidence]) {
        const badge = document.createElement("span");
        badge.className = "badge";
        badge.textContent = CONFIDENCE_WARNINGS[confidence];
        card.appendChild(badge);

        if (reasoning) {
            const why = document.createElement("p");
            why.className = "reasoning";
            why.textContent = reasoning;
            card.appendChild(why);
        }
    }

    return card;
}

function togglePageImage(card, imageData) {
    const existing = card.querySelector(".page-preview");
    if (existing) {
        existing.remove();
        return;
    }
    const img = document.createElement("img");
    img.className = "page-preview";
    img.src = `data:image/png;base64,${imageData}`;
    card.appendChild(img);
}
