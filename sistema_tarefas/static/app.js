async function postAction(url, taskId){
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type":"application/x-www-form-urlencoded"},
    body: new URLSearchParams({task_id: taskId})
  });
  let data = {};
  try { data = await response.json(); } catch (error) { throw new Error("Não foi possível concluir a ação. Tente novamente."); }
  if (!response.ok) throw new Error(data.message || "Você não tem permissão para realizar esta ação.");
  return data;
}
function showActionError(error){ alert(error.message || "Não foi possível concluir a ação. Tente novamente."); }
function advanceTask(id){ postAction("/task/advance", id).then(result => { if (result.ok) return location.reload(); if (result.done) return alert("Essa tarefa já está na última etapa."); alert(result.message || "Não foi possível avançar esta tarefa."); }).catch(showActionError); }
function backTask(id){ postAction("/task/back", id).then(result => { if (result.ok) return location.reload(); if (result.start) return alert("Essa tarefa já está na primeira etapa."); alert(result.message || "Não foi possível voltar esta tarefa."); }).catch(showActionError); }
function openTaskModal(columnId){ document.getElementById("modalColumn").value = columnId; new bootstrap.Modal(document.getElementById("taskModal")).show(); }

function confirmUserDeletion(name){
  const typed = window.prompt(`Para confirmar, digite exatamente o nome do usuário: ${name}`);
  if (typed !== name) { window.alert("O nome não confere. A exclusão foi cancelada."); return false; }
  return window.confirm(`Excluir ${name}? As tarefas serão mantidas, mas os acessos e notificações serão removidos.`);
}

document.addEventListener("DOMContentLoaded", () => {
  const themeToggle = document.querySelector("[data-theme-toggle]");
  const updateThemeButton = () => {
    if (!themeToggle) return;
    const dark = document.documentElement.dataset.theme === "dark";
    themeToggle.setAttribute("aria-pressed", String(dark));
    themeToggle.innerHTML = dark ? "Modo claro" : "Modo escuro";
  };
  if (themeToggle) {
    updateThemeButton();
    themeToggle.addEventListener("click", () => {
      const dark = document.documentElement.dataset.theme !== "dark";
      document.documentElement.dataset.theme = dark ? "dark" : "light";
      localStorage.setItem("tarefas-theme", dark ? "dark" : "light");
      updateThemeButton();
    });
  }
  const search = document.getElementById("user-search");
  const empty = document.getElementById("search-empty");
  if (!search) return;
  search.addEventListener("input", () => {
    const term = search.value.trim().toLowerCase();
    let visible = 0;
    document.querySelectorAll("#user-list .user-row").forEach(row => {
      const matches = !term || row.dataset.userSearch.includes(term);
      row.hidden = !matches;
      if (matches) visible += 1;
    });
    if (empty) empty.hidden = visible !== 0;
  });
});
