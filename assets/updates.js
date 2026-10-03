// Version page navigation as well as assets; accepting a release applies site-wide.
const script = document.currentScript;
const currentVersion = script.dataset.version;
const manifest = new URL(script.dataset.manifest, location.href);
const basePath = manifest.pathname.slice(0, -'version.json'.length);
const storageKey = `clavesol:accepted:${basePath}`;
const validVersion = version => /^[a-f0-9]{20}$/.test(version);
let checking = false, lastCheck = 0, notice, dismissedVersion;
function acceptedVersion() {
  try { return localStorage.getItem(storageKey); } catch { return null; }
}
function accept(version) {
  try { localStorage.setItem(storageKey, version); } catch { /* Storage may be disabled. */ }
}
function versionLinks(version) {
  for (const link of document.querySelectorAll('a[href]')) {
    const href = link.getAttribute('href');
    if (!href || href.startsWith('#') || link.hasAttribute('download')) continue;
    const url = new URL(href, location.href);
    if (url.origin !== manifest.origin || !url.pathname.startsWith(basePath)) continue;
    if (!url.pathname.endsWith('/') && !url.pathname.endsWith('.html')) continue;
    url.searchParams.set('_cs', version);
    url.searchParams.delete('_cs_retry');
    link.href = url.href;
  }
}
function destination(version, retry = false) {
  const url = new URL(location.href);
  url.searchParams.set('_cs', version);
  url.searchParams.delete('_cs_retry');
  if (retry) url.searchParams.set('_cs_retry', String(Date.now()));
  return url.href;
}
function removeNotice() { notice?.remove(); notice = null; }
async function checkForUpdate(onNavigation = false) {
  if (document.hidden || checking || Date.now() - lastCheck < 60000) return;
  checking = true;
  lastCheck = Date.now();
  try {
    const url = new URL(manifest);
    url.searchParams.set('check', String(Date.now()));
    const response = await fetch(url, {cache: 'no-store'});
    if (!response.ok) return;
    const {version} = await response.json();
    if (!validVersion(version)) return;
    if (version === currentVersion) {
      accept(version); removeNotice(); return;
    }
    // Only recover an accepted release on entry/history restoration, never
    // replace a page on a visibility check while someone may be playing music.
    const alreadyAccepted = acceptedVersion() === version;
    const requestedVersion = new URL(location.href).searchParams.get('_cs');
    if (alreadyAccepted) versionLinks(version);
    if (onNavigation && alreadyAccepted && requestedVersion !== version) {
      location.replace(destination(version));
      return;
    }
    if (notice || dismissedVersion === version) return;
    notice = document.createElement('div');
    notice.className = 'update-notice';
    notice.setAttribute('role', 'status');
    const message = document.createElement('span');
    const waiting = requestedVersion === version;
    message.textContent = waiting
      ? 'A versão atualizada ainda não chegou a esta página. Tente novamente em instantes.'
      : 'Uma nova versão do Clave Sol está disponível.';
    const link = document.createElement('a');
    link.textContent = waiting ? 'Tentar novamente' : 'Atualizar';
    link.href = destination(version, waiting);
    link.addEventListener('click', () => {
      accept(version);
      versionLinks(version);
      // Keep an explicit retry uncached, even if propagation is still delayed.
      link.href = destination(version, waiting);
    });
    const dismiss = document.createElement('button');
    dismiss.type = 'button';
    dismiss.textContent = 'Depois';
    dismiss.addEventListener('click', () => { dismissedVersion = version; removeNotice(); });
    notice.append(message, link, dismiss);
    document.body.append(notice);
  } catch {
    // Offline or unavailable endpoint: keep the current page usable.
  } finally {
    checking = false;
  }
}
if (validVersion(currentVersion)) versionLinks(currentVersion);
checkForUpdate(true);
document.addEventListener('visibilitychange', () => checkForUpdate(false));
window.addEventListener('pageshow', event => {
  if (!event.persisted) return;
  removeNotice(); lastCheck = 0;
  checkForUpdate(true);
});
