// Dark/Light mode aur accent color NEXORA mein save + apply karta hai

function nxApply() {
  var theme = localStorage.getItem('nx-theme') || 'light';
  var accent = localStorage.getItem('nx-accent') || 'blue';
  document.documentElement.setAttribute('data-theme', theme);
  document.documentElement.setAttribute('data-accent', accent);

  var sw = document.getElementById('nx-darkswitch');
  if (sw) sw.checked = (theme === 'dark');

  ['blue', 'purple', 'green'].forEach(function (c) {
    var el = document.getElementById('nx-' + c);
    if (el) el.className = 'dot ' + c + (accent === c ? ' on' : '');
  });
}

function nxSet(key, val) {
  localStorage.setItem('nx-' + key, val);
  nxApply();
}

function nxToggleDark(checked) {
  nxSet('theme', checked ? 'dark' : 'light');
}

function nxTogglePw(id) {
  var el = document.getElementById(id);
  var btn = el.nextElementSibling;
  if (el.type === 'password') {
    el.type = 'text';
    btn.textContent = 'Hide';
  } else {
    el.type = 'password';
    btn.textContent = 'Show';
  }
}

nxApply();
