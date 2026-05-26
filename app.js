const mode = document.body.dataset.mode || '1v1';
const currentScores = {
  '1v1': 169,
  '2v2': 274,
  '3v3': 442
};
const FIREBASE_CONFIG = window.FIREBASE_CONFIG || null;
const hasFirebase = typeof firebase !== 'undefined' && FIREBASE_CONFIG && FIREBASE_CONFIG.apiKey;

const gameForm = document.getElementById('gameForm');
const gameList = document.getElementById('gameList');
const pointsInput = document.getElementById('points');
const quickPoints = document.querySelectorAll('.quick-point');
const totalGames = document.getElementById('totalGames');
const averagePoints = document.getElementById('averagePoints');
const currentScore = document.getElementById('currentScore');
const winRate = document.getElementById('winRate');
const bestWinStreak = document.getElementById('bestWinStreak');
const bestLoseStreak = document.getElementById('bestLoseStreak');
const formMessage = document.getElementById('formMessage');
const clearAll = document.getElementById('clearAll');
const newSession = document.getElementById('newSession');
const resetZoom = document.getElementById('resetZoom');
const googleSignIn = document.getElementById('googleSignIn');
const googleSignOut = document.getElementById('googleSignOut');
const userLabel = document.getElementById('userLabel');
const baseScoreInput = document.getElementById('baseScoreInput');
const saveBaseScore = document.getElementById('saveBaseScore');
const pagination = document.getElementById('pagination');
const chartCanvas = document.getElementById('pointsChart');
const ctx = chartCanvas ? chartCanvas.getContext('2d') : null;
let chart;
let editingId = null;
let realtimeDb = null;
let firebaseAuth = null;
let currentUser = null;
let baseScoreOverride = null;
let currentPage = 1;

const GAMES_PER_PAGE = 10;

const STORAGE_KEY = `games_${mode}`;
const SESSION_START_KEY = `session_start_${mode}`;
const SESSION_ACTIVE_KEY = `session_active_${mode}`;
const CHART_MAX_GAMES = 50;

function updateAdaptivePointRadius(activeChart) {
  if (!activeChart || !activeChart.data?.datasets?.length) return;
  const xScale = activeChart.scales?.x;
  const dataset = activeChart.data.datasets[0];
  if (!xScale || !dataset) return;

  const totalLabels = activeChart.data.labels?.length || 0;
  if (!totalLabels) return;

  const minRaw = Number.isFinite(xScale.min) ? Number(xScale.min) : 0;
  const maxRaw = Number.isFinite(xScale.max) ? Number(xScale.max) : (totalLabels - 1);

  const minIndex = Math.max(0, Math.floor(minRaw));
  const maxIndex = Math.min(totalLabels - 1, Math.ceil(maxRaw));
  const visiblePoints = Math.max(1, (maxIndex - minIndex) + 1);

  let radius = 4;
  if (visiblePoints > 220) radius = 0;
  else if (visiblePoints > 140) radius = 1;
  else if (visiblePoints > 80) radius = 2;

  dataset.pointRadius = radius;
  dataset.pointHoverRadius = Math.max(6, radius + 4);
}

function isSessionActive() {
  return localStorage.getItem(SESSION_ACTIVE_KEY) === '1';
}

function setSessionActive(isActive) {
  if (isActive) {
    localStorage.setItem(SESSION_ACTIVE_KEY, '1');
    return;
  }
  localStorage.removeItem(SESSION_ACTIVE_KEY);
}

function updateSessionButtonLabel() {
  if (!newSession) return;
  newSession.textContent = isSessionActive() ? 'Termina sessione' : 'Nuova sessione';
}

function getSessionStartIndex() {
  const raw = localStorage.getItem(SESSION_START_KEY);
  const parsed = Number(raw);
  return Number.isNaN(parsed) || parsed < 0 ? 0 : parsed;
}

function setSessionStartIndex(index) {
  localStorage.setItem(SESSION_START_KEY, String(Math.max(0, index)));
}

function showMessage(text, isError = true) {
  if (!formMessage) return;
  formMessage.textContent = text;
  formMessage.style.color = isError ? '#ffb3b3' : '#b9ffd6';
}

function getLocalSavedGames() {
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored ? JSON.parse(stored) : [];
}

function persistLocalGames(games) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(games));
}

function getRomeDateTimeParts() {
  const now = new Date();
  const parts = new Intl.DateTimeFormat('it-IT', {
    timeZone: 'Europe/Rome',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).formatToParts(now);

  const map = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return {
    year: map.year,
    month: map.month,
    day: map.day,
    hour: map.hour,
    minute: map.minute,
    second: now.getSeconds(),
    millisecond: now.getMilliseconds()
  };
}

function setTodayAsDefaultDate() {
  const dateInput = document.getElementById('date');
  if (!dateInput) return;
  const now = getRomeDateTimeParts();
  dateInput.value = `${now.year}-${now.month}-${now.day}`;
}

function setCurrentTimeAsDefault() {
  const timeInput = document.getElementById('time');
  if (!timeInput) return;
  const now = getRomeDateTimeParts();
  timeInput.value = `${now.hour}:${now.minute}`;
}

function setupAutoTimeUpdate() {
  const timeInput = document.getElementById('time');
  if (!timeInput) return;

  let userIsEditingTime = false;

  timeInput.addEventListener('focus', () => {
    userIsEditingTime = true;
  });

  timeInput.addEventListener('blur', () => {
    userIsEditingTime = false;
  });

  const syncTime = () => {
    if (userIsEditingTime) return;
    setCurrentTimeAsDefault();
  };

  const now = getRomeDateTimeParts();
  const delayToNextMinute = ((60 - now.second) * 1000) - now.millisecond;

  window.setTimeout(() => {
    syncTime();
    window.setInterval(syncTime, 60000);
  }, Math.max(0, delayToNextMinute));
}

function setupQuickPoints() {
  if (!pointsInput || !quickPoints.length) return;
  quickPoints.forEach(button => {
    button.addEventListener('click', () => {
      const value = Number(button.dataset.points);
      if (Number.isNaN(value)) return;
      pointsInput.value = value;
      pointsInput.dispatchEvent(new Event('input', { bubbles: true }));
      pointsInput.focus();
    });
  });
}

function getGamesPath() {
  const scope = currentUser?.uid ? `users/${currentUser.uid}` : 'guests/local';
  return `${scope}/modes/${mode}/games`;
}

function getProfilePath() {
  const scope = currentUser?.uid ? `users/${currentUser.uid}` : 'guests/local';
  return `${scope}/profiles/${mode}`;
}

function getDefaultBaseScore() {
  return currentScores[mode] ?? 0;
}

function getEffectiveBaseScore() {
  return Number.isFinite(baseScoreOverride) ? baseScoreOverride : getDefaultBaseScore();
}

function updateBaseScoreInput() {
  if (!baseScoreInput) return;
  baseScoreInput.value = String(getEffectiveBaseScore());
}

async function loadBaseScoreOverride() {
  if (!realtimeDb) {
    baseScoreOverride = null;
    updateBaseScoreInput();
    return;
  }

  try {
    const snapshot = await realtimeDb.ref(getProfilePath()).once('value');
    const profile = snapshot.val() || {};
    const parsed = Number(profile.baseScore);
    baseScoreOverride = Number.isFinite(parsed) ? parsed : null;
  } catch (error) {
    baseScoreOverride = null;
  }
  updateBaseScoreInput();
}

async function saveBaseScoreOverride(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    showMessage('Inserisci punteggio base valido.');
    return;
  }

  if (realtimeDb) {
    await realtimeDb.ref(getProfilePath()).update({
      baseScore: numeric,
      updatedAt: Date.now()
    });
  }

  baseScoreOverride = numeric;
  updateBaseScoreInput();
}

function updateAuthUI() {
  if (userLabel) {
    userLabel.textContent = currentUser?.displayName || currentUser?.email || 'Guest';
  }
  if (googleSignIn) {
    googleSignIn.style.display = currentUser ? 'none' : 'inline-flex';
  }
  if (googleSignOut) {
    googleSignOut.style.display = currentUser ? 'inline-flex' : 'none';
  }
}

function initFirebase() {
  if (!hasFirebase) return;
  if (!firebase.apps.length) {
    firebase.initializeApp(FIREBASE_CONFIG);
  }
  realtimeDb = firebase.database();
  if (firebase.auth) {
    firebaseAuth = firebase.auth();
  }
}

async function getSavedGames() {
  if (!realtimeDb) {
    return getLocalSavedGames();
  }

  try {
    const snapshot = await realtimeDb.ref(getGamesPath()).once('value');
    const gamesMap = snapshot.val() || {};
    const games = Object.entries(gamesMap).map(([id, data]) => {
      return {
        id,
        date: data.date || '',
        time: data.time || '',
        points: Number(data.points) || 0
      };
    });
    games.sort((a, b) => new Date(a.date) - new Date(b.date));
    return games;
  } catch (error) {
    showMessage('Firebase non risponde, uso localStorage.', true);
    return getLocalSavedGames();
  }
}

async function addGame(game) {
  if (realtimeDb) {
    const ref = realtimeDb.ref(getGamesPath()).push();
    await ref.set({
        date: game.date,
        time: game.time || '',
        points: Number(game.points) || 0,
        createdAt: Date.now()
      });
    return;
  }
  const games = getLocalSavedGames();
  const nextId = games.length ? Math.max(...games.map(g => g.id)) + 1 : 1;
  games.push({ id: nextId, ...game });
  persistLocalGames(games);
}

async function updateGame(id, newData) {
  if (realtimeDb) {
    await realtimeDb.ref(`${getGamesPath()}/${String(id)}`).update({
        date: newData.date,
        time: newData.time || '',
        points: Number(newData.points) || 0,
        updatedAt: Date.now()
      });
    return;
  }
  const games = getLocalSavedGames();
  const index = games.findIndex(g => g.id === id);
  if (index === -1) return;
  games[index] = { ...games[index], ...newData };
  persistLocalGames(games);
}

async function deleteGame(id) {
  if (realtimeDb) {
    await realtimeDb.ref(`${getGamesPath()}/${String(id)}`).remove();
    return;
  }
  const games = getLocalSavedGames().filter(g => g.id !== id);
  persistLocalGames(games);
}

async function clearAllGames() {
  if (realtimeDb) {
    await realtimeDb.ref(getGamesPath()).remove();
    return;
  }
  localStorage.removeItem(STORAGE_KEY);
}

function buildRow(game, index) {
  const row = document.createElement('tr');
  row.innerHTML = `
    <td>${index + 1}</td>
    <td>${game.date}</td>
    <td>${game.time || '-'}</td>
    <td>${game.points}</td>
    <td>
      <button class="action-button edit" data-id="${String(game.id)}">Modifica</button>
      <button class="action-button delete" data-id="${String(game.id)}">Elimina</button>
    </td>
  `;
  return row;
}

function buildPagination(totalGamesCount, page) {
  if (!pagination) return;
  const totalPages = Math.max(1, Math.ceil(totalGamesCount / GAMES_PER_PAGE));
  pagination.innerHTML = '';

  if (totalGamesCount <= GAMES_PER_PAGE) return;

  const createButton = (label, targetPage, isActive = false, isDisabled = false) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `page-btn${isActive ? ' active' : ''}`;
    button.textContent = label;
    button.disabled = isDisabled;
    button.dataset.page = String(targetPage);
    return button;
  };

  pagination.appendChild(createButton('‹', page - 1, false, page <= 1));

  for (let p = 1; p <= totalPages; p += 1) {
    pagination.appendChild(createButton(String(p), p, p === page, false));
  }

  pagination.appendChild(createButton('›', page + 1, false, page >= totalPages));
}

function updateStats(games) {
  const total = games.length;
  const sessionStart = Math.min(getSessionStartIndex(), total);
  const sessionGames = games.slice(sessionStart);
  const allPoints = games.map(g => Number(g.points) || 0);
  const points = sessionGames.map(g => Number(g.points) || 0);
  const balance = points.reduce((sum, value) => sum + value, 0);
  const baseScore = getEffectiveBaseScore();
  const overallBalance = allPoints.reduce((sum, value) => sum + value, 0);
  const realCurrentScore = baseScore + overallBalance;

  let wins = 0;
  let losses = 0;
  let currentWinStreak = 0;
  let currentLoseStreak = 0;
  let topWinStreak = 0;
  let topLoseStreak = 0;

  points.forEach(value => {
    if (value > 0) {
      wins += 1;
      currentWinStreak += 1;
      currentLoseStreak = 0;
      topWinStreak = Math.max(topWinStreak, currentWinStreak);
      return;
    }

    if (value < 0) {
      losses += 1;
      currentLoseStreak += 1;
      currentWinStreak = 0;
      topLoseStreak = Math.max(topLoseStreak, currentLoseStreak);
      return;
    }

    currentWinStreak = 0;
    currentLoseStreak = 0;
  });

  const decidedGames = wins + losses;
  const sessionWinRate = decidedGames > 0 ? (wins / decidedGames) * 100 : 0;

  totalGames.innerHTML = `<span class="games-level">${total}</span><small class="games-real-total">${sessionGames.length}</small>`;

  averagePoints.textContent = `${balance >= 0 ? '+' : ''}${balance}`;
  currentScore.textContent = realCurrentScore;
  if (winRate) winRate.textContent = `${sessionWinRate.toFixed(1)}%`;
  if (bestWinStreak) bestWinStreak.textContent = String(topWinStreak);
  if (bestLoseStreak) bestLoseStreak.textContent = String(topLoseStreak);
}

function buildChart(games) {
  if (!ctx || typeof Chart === 'undefined') return;

  const sorted = [...games].sort((a, b) => new Date(a.date) - new Date(b.date));

  const selectedRange = 'all';

  const safeMaxGames = selectedRange === 'all'
    ? sorted.length
    : Math.max(1, Number.isNaN(selectedRange) ? CHART_MAX_GAMES : selectedRange);

  const visibleGames = safeMaxGames >= sorted.length
    ? sorted
    : sorted.slice(-safeMaxGames);

  const visibleStartIndex = sorted.length - visibleGames.length;
  const deltaValues = visibleGames.map(g => Number(g.points) || 0);
  const labels = visibleGames.map((game, index) => `G${visibleStartIndex + index + 1} - ${game.date}`);
  const values = deltaValues.reduce((acc, points) => {
    const last = acc.length ? acc[acc.length - 1] : 0;
    acc.push(last + points);
    return acc;
  }, []);

  const packedValues = values.length > 300
    ? values.filter((_, index) => index % Math.ceil(values.length / 300) === 0)
    : values;
  const packedLabels = labels.length > 300
    ? labels.filter((_, index) => index % Math.ceil(labels.length / 300) === 0)
    : labels;
  const packedDeltas = deltaValues.length > 300
    ? deltaValues.filter((_, index) => index % Math.ceil(deltaValues.length / 300) === 0)
    : deltaValues;

  const chartLabels = packedValues.length ? packedLabels : ['Nessuna partita in sessione'];
  const chartValues = packedValues.length ? packedValues : [0];
  const tooltipDeltas = packedValues.length ? packedDeltas : [0];

  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: chartLabels,
      datasets: [{
        label: 'Punteggio totale',
        data: chartValues,
        borderColor: '#7da7ff',
        backgroundColor: 'rgba(125, 167, 255, 0.16)',
        fill: true,
        tension: 0.32,
        pointRadius: chartValues.length > 120 ? 0 : 3,
        pointHoverRadius: 8,
        pointHitRadius: 14,
        borderWidth: 2.6,
        spanGaps: true
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      scales: {
        x: {
          ticks: {
            color: '#c5d1ff',
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: 10
          },
          grid: { color: 'rgba(255,255,255,0.06)' }
        },
        y: {
          beginAtZero: false,
          ticks: { color: '#c5d1ff' },
          grid: { color: 'rgba(255,255,255,0.08)' }
        }
      },
      plugins: {
        decimation: {
          enabled: chartValues.length > 120,
          algorithm: 'lttb',
          samples: 120
        },
        zoom: {
          pan: {
            enabled: true,
            mode: 'x',
            modifierKey: 'shift'
          },
          zoom: {
            wheel: {
              enabled: true
            },
            pinch: {
              enabled: true
            },
            drag: {
              enabled: true,
              borderColor: 'rgba(125,167,255,0.8)',
              borderWidth: 1,
              backgroundColor: 'rgba(125,167,255,0.12)'
            },
            mode: 'x',
            onZoomComplete({ chart: activeChart }) {
              updateAdaptivePointRadius(activeChart);
              activeChart.update('none');
            }
          },
          onPanComplete({ chart: activeChart }) {
            updateAdaptivePointRadius(activeChart);
            activeChart.update('none');
          },
          limits: {
            x: { minRange: 8 }
          }
        },
        legend: { labels: { color: '#d2d9ff' } },
        tooltip: {
          mode: 'index',
          intersect: false,
          callbacks: {
            title(items) {
              if (!items.length) return '';
              return items[0].label;
            },
            label(context) {
              const totalValue = context.parsed.y;
              const delta = tooltipDeltas[context.dataIndex] ?? 0;
              const signedDelta = `${delta >= 0 ? '+' : ''}${delta}`;
              return `Totale: ${totalValue} | Delta: ${signedDelta}`;
            }
          }
        }
      }
    }
  });

  updateAdaptivePointRadius(chart);
  chart.update('none');
}

async function refresh() {
  try {
    const games = await getSavedGames();
    const totalPages = Math.max(1, Math.ceil(games.length / GAMES_PER_PAGE));
    currentPage = Math.min(Math.max(1, currentPage), totalPages);
    const start = (currentPage - 1) * GAMES_PER_PAGE;
    const pageGames = games.slice(start, start + GAMES_PER_PAGE);

    gameList.innerHTML = '';
    pageGames.forEach((game, index) => gameList.appendChild(buildRow(game, start + index)));
    buildPagination(games.length, currentPage);
    updateStats(games);
    buildChart(games);
  } catch (error) {
    showMessage(error.message || 'Errore durante aggiornamento dashboard.');
  }
}

gameForm.addEventListener('submit', async event => {
  event.preventDefault();
  const dateValue = document.getElementById('date').value;
  const timeValue = document.getElementById('time').value;
  const pointsValue = Number(document.getElementById('points').value);
  if (!dateValue || Number.isNaN(pointsValue)) {
    showMessage('Inserisci data e punteggio validi.');
    return;
  }

  try {
    if (editingId) {
      await updateGame(editingId, { date: dateValue, time: timeValue, points: pointsValue });
      showMessage('Partita aggiornata con successo.', false);
      editingId = null;
    } else {
      await addGame({ date: dateValue, time: timeValue, points: pointsValue });
      showMessage('Partita salvata con successo.', false);
    }
    gameForm.reset();
    setTodayAsDefaultDate();
    setCurrentTimeAsDefault();
    refresh();
  } catch (error) {
    showMessage(error.message || 'Errore durante il salvataggio.');
  }
});

if (pagination) {
  pagination.addEventListener('click', event => {
    const button = event.target.closest('button.page-btn');
    if (!button || button.disabled) return;
    const nextPage = Number(button.dataset.page);
    if (Number.isNaN(nextPage) || nextPage < 1 || nextPage === currentPage) return;
    currentPage = nextPage;
    refresh();
  });
}

gameList.addEventListener('click', async event => {
  const button = event.target.closest('button');
  if (!button) return;
  const id = button.dataset.id;
  const localId = Number(id);

  if (button.classList.contains('edit')) {
    const games = await getSavedGames();
    const game = games.find(g => String(g.id) === id);
    if (!game) return;
    document.getElementById('date').value = game.date;
    document.getElementById('time').value = game.time || '';
    document.getElementById('points').value = game.points;
    editingId = realtimeDb ? id : (Number.isNaN(localId) ? id : localId);
  }

  if (button.classList.contains('delete')) {
    try {
      await deleteGame(realtimeDb ? id : (Number.isNaN(localId) ? id : localId));
      showMessage('Partita eliminata.', false);
      refresh();
    } catch (error) {
      showMessage(error.message || 'Errore durante l’eliminazione.');
    }
  }
});

initFirebase();
setTodayAsDefaultDate();
setCurrentTimeAsDefault();
setupQuickPoints();
setupAutoTimeUpdate();

if (firebaseAuth) {
  firebaseAuth.onAuthStateChanged(async user => {
    currentUser = user || null;
    updateAuthUI();
    await loadBaseScoreOverride();
    refresh();
  });
}

if (googleSignIn && firebaseAuth) {
  googleSignIn.addEventListener('click', async () => {
    try {
      const provider = new firebase.auth.GoogleAuthProvider();
      await firebaseAuth.signInWithPopup(provider);
      showMessage('Accesso Google completato.', false);
    } catch (error) {
      showMessage(error.message || 'Errore durante accesso Google.');
    }
  });
}

if (googleSignOut && firebaseAuth) {
  googleSignOut.addEventListener('click', async () => {
    try {
      await firebaseAuth.signOut();
      showMessage('Disconnesso.', false);
    } catch (error) {
      showMessage(error.message || 'Errore durante logout.');
    }
  });
}

updateAuthUI();
loadBaseScoreOverride();

if (saveBaseScore) {
  saveBaseScore.addEventListener('click', async () => {
    try {
      await saveBaseScoreOverride(baseScoreInput ? baseScoreInput.value : '');
      refresh();
      showMessage('Punteggio base personale salvato.', false);
    } catch (error) {
      showMessage(error.message || 'Errore salvataggio punteggio base.');
    }
  });
}

clearAll.addEventListener('click', async () => {
  const firstConfirm = window.confirm('Sei sicuro di voler eliminare TUTTO l’elenco partite?');
  if (!firstConfirm) return;

  const secondConfirm = window.confirm('Conferma finale: questa azione è irreversibile. Vuoi davvero cancellare tutto?');
  if (!secondConfirm) return;

  try {
    await clearAllGames();
    setSessionStartIndex(0);
    setSessionActive(false);
    updateSessionButtonLabel();
    editingId = null;
    gameForm.reset();
    setTodayAsDefaultDate();
    setCurrentTimeAsDefault();
    refresh();
    showMessage('Tutte le partite sono state cancellate.', false);
  } catch (error) {
    showMessage(error.message || 'Errore durante il reset.');
  }
});

if (newSession) {
  newSession.addEventListener('click', async () => {
    try {
      if (!isSessionActive()) {
        const games = await getSavedGames();
        setSessionStartIndex(games.length);
        setSessionActive(true);
        updateSessionButtonLabel();
        refresh();
        showMessage('Nuova sessione avviata: bilancio azzerato da ora.', false);
        return;
      }

      setSessionStartIndex(0);
      setSessionActive(false);
      updateSessionButtonLabel();
      editingId = null;
      gameForm.reset();
      setTodayAsDefaultDate();
      setCurrentTimeAsDefault();
      refresh();
      showMessage('Sessione terminata: dashboard tornata ai valori di default.', false);
    } catch (error) {
      showMessage(error.message || 'Errore durante avvio nuova sessione.');
    }
  });
}

if (resetZoom) {
  resetZoom.addEventListener('click', () => {
    if (!chart) return;
    chart.resetZoom();
    updateAdaptivePointRadius(chart);
    chart.update('none');
  });
}

updateSessionButtonLabel();
refresh();
