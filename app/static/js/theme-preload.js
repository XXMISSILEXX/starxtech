(() => {
  const root = document.documentElement;
  const appearances = new Set(['system', 'light', 'dark']);
  const accents = new Set(['blue', 'green', 'purple', 'orange']);
  const scheme = window.matchMedia?.('(prefers-color-scheme: dark)');

  const valid = (value) => ({
    appearance: appearances.has(value?.appearance) ? value.appearance : root.dataset.appearance || 'system',
    accent: accents.has(value?.accent) ? value.accent : root.dataset.accent || 'blue',
  });
  const preferences = () => valid({ appearance: root.dataset.appearance, accent: root.dataset.accent });
  const resolvedTheme = (appearance) => appearance === 'system' ? (scheme?.matches ? 'dark' : 'light') : appearance;
  const applyChartDefaults = () => {
    if (!window.Chart) return;
    const styles = getComputedStyle(root);
    window.Chart.defaults.color = styles.getPropertyValue('--sx-chart-text').trim();
    window.Chart.defaults.borderColor = styles.getPropertyValue('--sx-chart-grid').trim();
    Object.values(window.Chart.instances || {}).forEach((chart) => chart.update('none'));
  };
  const apply = (value) => {
    const next = valid(value);
    root.dataset.appearance = next.appearance;
    root.dataset.accent = next.accent;
    root.dataset.resolvedTheme = resolvedTheme(next.appearance);
    root.dataset.bsTheme = root.dataset.resolvedTheme;
    applyChartDefaults();
    window.dispatchEvent(new CustomEvent('starx:themechange', { detail: next }));
    return next;
  };
  const storageKey = root.dataset.themeStorageKey;
  const readStored = () => {
    if (!storageKey) return null;
    try {
      const saved = JSON.parse(window.localStorage.getItem(storageKey));
      return appearances.has(saved?.appearance) && accents.has(saved?.accent) ? saved : null;
    } catch (_error) {
      return null;
    }
  };
  const store = (value) => {
    const next = valid(value);
    if (storageKey) {
      try { window.localStorage.setItem(storageKey, JSON.stringify(next)); } catch (_error) { /* private storage can be unavailable */ }
    }
    return next;
  };

  window.StarXTheme = { apply, applyChartDefaults, preferences, store };
  apply(readStored() || preferences());
  const followSystem = () => {
    if (preferences().appearance === 'system') apply(preferences());
  };
  if (scheme?.addEventListener) scheme.addEventListener('change', followSystem);
  else if (scheme?.addListener) scheme.addListener(followSystem);
})();
