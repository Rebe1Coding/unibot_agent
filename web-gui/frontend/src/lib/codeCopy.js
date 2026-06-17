/** Добавляет кнопку «Копировать» к каждому блоку кода внутри отрендеренного markdown. */
export function attachCopyButtons(root) {
  if (!root) return;
  root.querySelectorAll('pre').forEach((pre) => {
    if (pre.querySelector('.code-copy')) return;
    pre.classList.add('code-block');
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'code-copy';
    btn.textContent = 'Копировать';
    btn.addEventListener('click', () => {
      const code = pre.querySelector('code');
      const text = code ? code.innerText : pre.innerText;
      navigator.clipboard.writeText(text).then(() => {
        btn.textContent = 'Скопировано';
        setTimeout(() => { btn.textContent = 'Копировать'; }, 1500);
      }).catch(() => { btn.textContent = 'Ошибка'; });
    });
    pre.appendChild(btn);
  });
}
