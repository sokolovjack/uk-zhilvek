(() => {
  const areas = document.querySelectorAll("textarea.js-wysiwyg");
  if (!areas.length || typeof tinymce === "undefined") return;

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
      "undo redo | styles | bold italic underline | alignleft aligncenter alignright | bullist numlist | link image | table | removeformat | code",
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
      "body { font-family: Segoe UI, system-ui, sans-serif; font-size: 15px; line-height: 1.55; color: #1a2438; }",
    images_upload_url: "/admin/upload-image",
    automatic_uploads: true,
    images_upload_credentials: true,
    file_picker_types: "image",
    setup(editor) {
      editor.on("change keyup", () => editor.save());
    },
  });

  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", () => {
      if (window.tinymce) tinymce.triggerSave();
    });
  });
})();
