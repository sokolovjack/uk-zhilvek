(() => {
  const btn = document.querySelector(".burger");
  const nav = document.querySelector("nav.main");
  if (btn && nav) btn.addEventListener("click", () => nav.classList.toggle("open"));

  const q = document.querySelector("#houseSearch");
  if (q) {
    q.addEventListener("input", () => {
      const v = q.value.trim().toLowerCase();
      document.querySelectorAll(".house").forEach((el) => {
        el.style.display = el.dataset.name.toLowerCase().includes(v) ? "" : "none";
      });
    });
  }

  const form = document.querySelector("form.feedback");
  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const name = form.querySelector("[name=name]").value.trim();
      const contact = form.querySelector("[name=contact]").value.trim();
      const msg = form.querySelector("[name=message]").value.trim();
      const body = encodeURIComponent(`Имя: ${name}\nКонтакт: ${contact}\n\n${msg}`);
      window.location.href = `mailto:uk-zhilvek@mail.ru?subject=${encodeURIComponent("Обращение с сайта УК ЖилВек")}&body=${body}`;
      const ok = form.parentElement.querySelector(".ok-msg");
      if (ok) {
        ok.textContent = "Откройте письмо в почте и нажмите «Отправить» — адрес: uk-zhilvek@mail.ru";
        ok.classList.add("show");
      }
      form.reset();
    });
  }
})();
