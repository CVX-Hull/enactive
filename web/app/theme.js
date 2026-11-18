// Shared by the supervised and recorded pages, independently of their data paths.
const root = document.documentElement;
try { const saved = localStorage.getItem('theme'); if (saved === 'light' || saved === 'dark') root.dataset.theme = saved; } catch { /* no storage */ }
document.getElementById('theme').addEventListener('click', () => {
  const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  root.dataset.theme = dark ? 'light' : 'dark';
  try { localStorage.setItem('theme', root.dataset.theme); } catch { /* no storage */ }
  document.dispatchEvent(new CustomEvent('enactive:theme', {detail: {theme: root.dataset.theme}}));
});
