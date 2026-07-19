import { PANEL_PREFERENCES_STORAGE_KEY } from '@/features/shell/contracts/panel-preferences';

/**
 * Inline, render-blocking script that sets `data-theme` on the document root
 * before first paint, reading the same persisted preference the app uses so
 * there is no flash of the wrong theme (FOUC) on load. Kept deliberately tiny
 * and dependency-free; mirrors `resolveTheme` in `use-theme.ts`. Runs under the
 * app CSP (`script-src 'self' 'unsafe-inline'`), so no nonce is required.
 */
const themeScript = `(function(){try{var p='system';var raw=localStorage.getItem('${PANEL_PREFERENCES_STORAGE_KEY}');if(raw){var s=JSON.parse(raw);var t=s&&s.state&&s.state.panelPreferences&&s.state.panelPreferences.theme;if(t==='light'||t==='dark'||t==='system'){p=t;}}var r=p==='system'?(window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'):p;document.documentElement.setAttribute('data-theme',r);}catch(e){document.documentElement.setAttribute('data-theme','dark');}})();`;

export function ThemeScript() {
  return <script dangerouslySetInnerHTML={{ __html: themeScript }} />;
}
