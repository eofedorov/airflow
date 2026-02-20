(function () {
  const uploadForm = document.getElementById("upload-form");
  const uploadResult = document.getElementById("upload-result");
  const uploadBtn = document.getElementById("upload-btn");

  uploadForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    const fileInput = document.getElementById("upload-files");
    const files = fileInput.files;
    if (!files || files.length === 0) {
      setResult(uploadResult, "Выберите хотя бы один файл.", true);
      return;
    }
    setResult(uploadResult, "Загружаем…", false, true);
    uploadBtn.disabled = true;
    try {
      const formData = new FormData();
      for (let i = 0; i < files.length; i++) {
        formData.append("files", files[i]);
      }
      const res = await fetch("/rag/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setResult(uploadResult, data.detail || `Ошибка ${res.status}`, true);
        return;
      }
      setResult(
        uploadResult,
        `Загружено файлов: ${data.files_count}. ${data.message || ""}`,
        false
      );
    } catch (err) {
      setResult(uploadResult, "Ошибка сети: " + err.message, true);
    } finally {
      uploadBtn.disabled = false;
    }
  });

  function setResult(el, text, isError, loading) {
    el.textContent = text;
    el.className = "result" + (loading ? " loading" : "") + (isError ? " error" : "");
  }

  function setResultHtml(el, html, isError) {
    el.innerHTML = html;
    el.className = "result" + (isError ? " error" : "");
  }

  function esc(s) {
    if (s == null) return "";
    const t = String(s);
    return t
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  const searchForm = document.getElementById("search-form");
  const searchResult = document.getElementById("search-result");
  const searchBtn = document.getElementById("search-btn");

  searchForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    const q = document.getElementById("search-query").value.trim();
    const k = document.getElementById("search-k").value || "5";
    setResult(searchResult, "Ищем…", false, true);
    searchBtn.disabled = true;
    try {
      const res = await fetch(
        "/rag/search?q=" + encodeURIComponent(q) + "&k=" + encodeURIComponent(k)
      );
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        const msg = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : "Ошибка " + res.status;
        setResult(searchResult, msg, true);
        return;
      }
      const hits = Array.isArray(data) ? data : [];
      if (hits.length === 0) {
        setResult(searchResult, "Ничего не найдено.", false);
        return;
      }
      const html = hits
        .map(
          (h) =>
            '<div class="hit">' +
            '<div class="title">' + esc(h.doc_title || "—") + "</div>" +
            '<div class="path">' + esc(h.path) + "</div>" +
            '<div class="preview">' + esc(h.text_preview) + "</div>" +
            (h.score != null ? '<div class="score">' + esc(String(h.score)) + "</div>" : "") +
            "</div>"
        )
        .join("");
      setResultHtml(searchResult, html, false);
    } catch (err) {
      setResult(searchResult, "Ошибка сети: " + err.message, true);
    } finally {
      searchBtn.disabled = false;
    }
  });

  const askForm = document.getElementById("ask-form");
  const askResult = document.getElementById("ask-result");
  const askBtn = document.getElementById("ask-btn");

  askForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    const question = document.getElementById("ask-question").value.trim();
    if (!question) {
      setResult(askResult, "Введите вопрос.", true);
      return;
    }
    setResult(askResult, "Отправляем вопрос…", false, true);
    askBtn.disabled = true;
    try {
      const res = await fetch("/rag/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        const msg = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : "Ошибка " + res.status;
        setResult(askResult, msg, true);
        return;
      }
      const parts = [];
      parts.push('<div class="answer-block">' + esc(data.answer || "") + "</div>");
      if (data.confidence != null) {
        parts.push("<div>Уверенность: " + esc(String(data.confidence)) + "</div>");
      }
      if (data.status) {
        parts.push("<div>Статус: " + esc(data.status) + "</div>");
      }
      if (data.sources && data.sources.length > 0) {
        parts.push('<div class="sources">Источники:<br>');
        data.sources.forEach(function (s) {
          parts.push(
            '<div class="source">' +
              '<span class="doc-title">' + esc(s.doc_title) + "</span>" +
              (s.relevance != null ? " (релевантность: " + esc(String(s.relevance)) + ")" : "") +
              '<div class="quote">' + esc(s.quote) + "</div>" +
              "</div>"
          );
        });
        parts.push("</div>");
      }
      setResultHtml(askResult, parts.join(""), false);
    } catch (err) {
      setResult(askResult, "Ошибка сети: " + err.message, true);
    } finally {
      askBtn.disabled = false;
    }
  });
})();
