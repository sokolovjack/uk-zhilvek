(() => {
  const areas = document.querySelectorAll("textarea.js-wysiwyg");
  if (!areas.length || typeof tinymce === "undefined") return;

  const FILE_ACCEPT =
    ".pdf,.doc,.docx,.xls,.xlsx,.zip,.rtf,.jpg,.jpeg,.png,.webp,application/pdf";

  async function uploadFile(file) {
    const body = new FormData();
    body.append("file", file);
    const res = await fetch("/admin/upload-file", {
      method: "POST",
      body,
      credentials: "same-origin",
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || data.error || "Не удалось загрузить файл");
    }
    if (!data.location) {
      throw new Error("Сервер не вернул ссылку на файл");
    }
    return data;
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  tinymce.init({
    selector: "textarea.js-wysiwyg",
    license_key: "gpl",
    language: "ru",
    language_url: "https://cdn.jsdelivr.net/npm/tinymce-i18n@25.1.0/langs7/ru.js",
    base_url: "https://cdn.jsdelivr.net/npm/tinymce@7.6.1",
    suffix: ".min",
    menubar: "edit insert format table",
    plugins: "lists link image table code autoresize media",
    toolbar:
      "undo redo | styles | bold italic underline | alignleft aligncenter alignright | bullist numlist | link image uploadfile | table | removeformat | code",
    style_formats: [
      { title: "Абзац", format: "p" },
      { title: "Заголовок 2", format: "h2" },
      { title: "Заголовок 3", format: "h3" },
      { title: "Заголовок 4", format: "h4" },
    ],
    height: 460,
    min_height: 360,
    autoresize_bottom_margin: 24,
    branding: false,
    promotion: false,
    convert_urls: false,
    relative_urls: false,
    remove_script_host: false,
    content_style:
      "body { font-family: Segoe UI, system-ui, sans-serif; font-size: 15px; line-height: 1.55; color: #1a2438; }" +
      "a[href*='/uploads/'] { font-weight: 600; }",
    images_upload_url: "/admin/upload-image",
    automatic_uploads: true,
    images_upload_credentials: true,
    file_picker_types: "image",
    setup(editor) {
      editor.ui.registry.addButton("uploadfile", {
        text: "Файл",
        tooltip: "Вставить файл (PDF, DOC, XLS, ZIP…)",
        icon: "upload",
        onAction() {
          const input = document.createElement("input");
          input.type = "file";
          input.accept = FILE_ACCEPT;
          input.onchange = async () => {
            const file = input.files && input.files[0];
            if (!file) return;
            editor.setProgressState(true);
            try {
              const data = await uploadFile(file);
              const title = data.title || file.name || "Скачать файл";
              const isImage = /\.(jpe?g|png|webp)$/i.test(file.name || "");
              if (isImage) {
                editor.insertContent(
                  `<p><img src="${escapeHtml(data.location)}" alt="${escapeHtml(title)}"></p>`
                );
              } else {
                editor.insertContent(
                  `<p><a href="${escapeHtml(data.location)}" target="_blank" rel="noopener">${escapeHtml(title)}</a></p>`
                );
              }
              editor.save();
            } catch (err) {
              editor.notificationManager.open({
                type: "error",
                text: err.message || "Ошибка загрузки",
              });
            } finally {
              editor.setProgressState(false);
            }
          };
          input.click();
        },
      });

      editor.ui.registry.addMenuItem("uploadfile", {
        text: "Файл…",
        icon: "upload",
        onAction() {
          editor.execCommand("mceUploadFile");
        },
      });

      editor.addCommand("mceUploadFile", () => {
        const btn = editor.ui.registry.getAll().buttons.uploadfile;
        if (btn && btn.onAction) btn.onAction();
      });

      editor.on("change keyup", () => editor.save());
    },
  });

  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", () => {
      if (window.tinymce) tinymce.triggerSave();
    });
  });
})();
