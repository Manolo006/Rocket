const mode = document.body.dataset.mode || '1v1';
const currentScores = {
  '1v1': 0,
  '2v2': 0,
  '3v3': 0
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

const RANK_STYLE = {
  Bronze: { icon: '🥉', color: '#8b5a2b' },
  Silver: { icon: '⚪', color: '#c0c7d1' },
  Gold: { icon: '🟡', color: '#d6a21f' },
  Platinum: { icon: '💠', color: '#2fc6d6' },
  Diamond: { icon: '🔷', color: '#3478f6' },
  Champion: { icon: '🟣', color: '#7a3cff' },
  'Grand Champion': { icon: '🔴', color: '#d92f45' },
  'Supersonic Legend': { icon: '👑', color: '#f2e98f' }
};

const MODE_RANK_STARTS = {
  // Community MMR thresholds, split by playlist. Easy to update per season.
  '2v2': [
    ['Bronze I', 0], ['Bronze II', 176], ['Bronze III', 236],
    ['Silver I', 296], ['Silver II', 356], ['Silver III', 416],
    ['Gold I', 476], ['Gold II', 536], ['Gold III', 596],
    ['Platinum I', 656], ['Platinum II', 716], ['Platinum III', 776],
    ['Diamond I', 836], ['Diamond II', 916], ['Diamond III', 996],
    ['Champion I', 1076], ['Champion II', 1196], ['Champion III', 1316],
    ['Grand Champion I', 1436], ['Grand Champion II', 1556], ['Grand Champion III', 1676],
    ['Supersonic Legend', 1860]
  ],
  '3v3': [
    ['Bronze I', 0], ['Bronze II', 176], ['Bronze III', 236],
    ['Silver I', 296], ['Silver II', 356], ['Silver III', 416],
    ['Gold I', 476], ['Gold II', 536], ['Gold III', 596],
    ['Platinum I', 656], ['Platinum II', 716], ['Platinum III', 776],
    ['Diamond I', 836], ['Diamond II', 916], ['Diamond III', 996],
    ['Champion I', 1076], ['Champion II', 1196], ['Champion III', 1316],
    ['Grand Champion I', 1436], ['Grand Champion II', 1556], ['Grand Champion III', 1676],
    ['Supersonic Legend', 1860]
  ]
};

const MODE_RANK_RANGES = {
  '1v1': [
    ['Bronze I', [[-100, 113], [114, 127], [128, 141], [142, 154]]],
    ['Bronze II', [[147, 158], [159, 177], [178, 196], [197, 212]]],
    ['Bronze III', [[214, 218], [219, 237], [238, 256], [257, 264]]],
    ['Silver I', [[273, 278], [279, 297], [298, 316], [317, 326]]],
    ['Silver II', [[335, 338], [339, 357], [358, 376], [377, 382]]],
    ['Silver III', [[395, 398], [399, 417], [418, 436], [437, 452]]],
    ['Gold I', [[455, 458], [459, 477], [478, 496], [497, 514]]],
    ['Gold II', [[515, 518], [519, 537], [538, 556], [557, 571]]],
    ['Gold III', [[575, 578], [579, 597], [598, 616], [617, 633]]],
    ['Platinum I', [[635, 638], [639, 657], [658, 676], [677, 687]]],
    ['Platinum II', [[695, 698], [699, 717], [718, 736], [737, 746]]],
    ['Platinum III', [[755, 758], [759, 777], [778, 796], [797, 806]]],
    ['Diamond I', [[815, 818], [819, 837], [838, 856], [857, 874]]],
    ['Diamond II', [[874, 878], [879, 897], [898, 916], [917, 924]]],
    ['Diamond III', [[935, 938], [939, 957], [958, 976], [976, 983]]],
    ['Champion I', [[995, 998], [999, 1017], [1018, 1036], [1037, 1045]]],
    ['Champion II', [[1055, 1058], [1059, 1077], [1078, 1096], [1097, 1104]]],
    ['Champion III', [[1106, 1118], [1119, 1137], [1138, 1154], [1157, 1168]]],
    ['Grand Champion I', [[1175, 1178], [1179, 1197], [1198, 1209], [1217, 1230]]],
    ['Grand Champion II', [[1227, 1238], [1240, 1251], [1259, 1275], [1277, 1294]]],
    ['Grand Champion III', [[1282, 1298], [1300, 1314], [1318, 1334], [1336, 1354]]],
    ['Supersonic Legend', [[1345, 1602]]]
  ],
  '2v2': [
    ['Bronze I', [[-100, 118], [119, 137], [138, 156], [157, 161]]],
    ['Bronze II', [[168, 178], [179, 197], [198, 216], [217, 220]]],
    ['Bronze III', [[229, 238], [239, 257], [258, 276], [277, 284]]],
    ['Silver I', [[291, 298], [299, 317], [318, 336], [337, 346]]],
    ['Silver II', [[351, 358], [359, 377], [378, 396], [397, 405]]],
    ['Silver III', [[412, 418], [419, 437], [438, 456], [457, 465]]],
    ['Gold I', [[471, 478], [479, 497], [498, 516], [517, 526]]],
    ['Gold II', [[532, 538], [539, 557], [558, 576], [577, 585]]],
    ['Gold III', [[593, 598], [599, 617], [618, 636], [637, 645]]],
    ['Platinum I', [[652, 658], [659, 677], [678, 696], [697, 705]]],
    ['Platinum II', [[712, 718], [719, 737], [738, 756], [757, 765]]],
    ['Platinum III', [[767, 778], [779, 797], [798, 816], [817, 825]]],
    ['Diamond I', [[835, 843], [844, 867], [868, 891], [892, 901]]],
    ['Diamond II', [[914, 923], [924, 947], [948, 971], [972, 984]]],
    ['Diamond III', [[994, 1003], [1004, 1027], [1028, 1051], [1052, 1060]]],
    ['Champion I', [[1075, 1093], [1094, 1127], [1128, 1160], [1162, 1179]]],
    ['Champion II', [[1195, 1213], [1214, 1247], [1248, 1277], [1282, 1299]]],
    ['Champion III', [[1315, 1333], [1335, 1367], [1368, 1396], [1402, 1419]]],
    ['Grand Champion I', [[1435, 1457], [1462, 1495], [1498, 1526], [1537, 1559]]],
    ['Grand Champion II', [[1575, 1597], [1600, 1636], [1638, 1660], [1677, 1698]]],
    ['Grand Champion III', [[1715, 1735], [1744, 1774], [1788, 1815], [1832, 1858]]],
    ['Supersonic Legend', [[1860, 2107]]]
  ],
  '3v3': [
    ['Bronze I', [[-100, 118], [119, 137], [138, 156], [157, 171]]],
    ['Bronze II', [[173, 178], [179, 197], [198, 216], [217, 231]]],
    ['Bronze III', [[229, 238], [239, 257], [258, 276], [277, 286]]],
    ['Silver I', [[295, 298], [299, 317], [318, 336], [337, 354]]],
    ['Silver II', [[355, 358], [359, 377], [378, 396], [397, 402]]],
    ['Silver III', [[415, 418], [419, 437], [438, 456], [457, 470]]],
    ['Gold I', [[475, 478], [479, 497], [498, 516], [517, 532]]],
    ['Gold II', [[535, 538], [539, 557], [558, 576], [577, 585]]],
    ['Gold III', [[595, 598], [599, 617], [618, 636], [637, 642]]],
    ['Platinum I', [[655, 658], [659, 677], [678, 696], [697, 705]]],
    ['Platinum II', [[715, 718], [719, 737], [738, 756], [757, 774]]],
    ['Platinum III', [[775, 778], [779, 797], [798, 816], [817, 825]]],
    ['Diamond I', [[835, 843], [844, 867], [868, 891], [892, 901]]],
    ['Diamond II', [[915, 923], [924, 947], [948, 971], [972, 980]]],
    ['Diamond III', [[995, 1003], [1004, 1027], [1028, 1051], [1052, 1060]]],
    ['Champion I', [[1075, 1093], [1094, 1127], [1128, 1161], [1162, 1180]]],
    ['Champion II', [[1195, 1213], [1214, 1247], [1248, 1280], [1282, 1300]]],
    ['Champion III', [[1315, 1333], [1334, 1367], [1368, 1398], [1402, 1420]]],
    ['Grand Champion I', [[1435, 1458], [1460, 1486], [1499, 1533], [1537, 1559]]],
    ['Grand Champion II', [[1575, 1598], [1600, 1634], [1638, 1660], [1677, 1699]]],
    ['Grand Champion III', [[1704, 1741], [1745, 1777], [1788, 1821], [1832, 1858]]],
    ['Supersonic Legend', [[1866, 1963]]]
  ]
};

function buildRankTable(rankStarts) {
  return rankStarts.flatMap(([name, start], index) => {
    const [family] = name.startsWith('Grand Champion')
      ? ['Grand Champion']
      : name.startsWith('Supersonic Legend')
        ? ['Supersonic Legend']
        : [name.split(' ')[0]];
    const style = RANK_STYLE[family];
    const nextStart = rankStarts[index + 1]?.[1] ?? Infinity;
    const span = nextStart - start;

    if (!Number.isFinite(span) || name === 'Supersonic Legend') {
      return [{ name, short: 'SSL', min: start, max: Infinity, icon: style.icon, color: style.color }];
    }

    const divSize = Math.max(1, Math.floor(span / 4));
    return ['I', 'II', 'III', 'IV'].map((division, divIndex) => {
      const min = start + (divSize * divIndex);
      const max = divIndex === 3 ? nextStart - 1 : start + (divSize * (divIndex + 1)) - 1;
      const shortFamily = family === 'Grand Champion' ? 'GC' : family[0];
      return {
        name: `${name} Div ${division}`,
        short: `${shortFamily}${name.match(/\b(I|II|III)$/)?.[0] || ''}.${divIndex + 1}`,
        min,
        max,
        icon: style.icon,
        color: style.color
      };
    });
  });
}

function getRankFamily(name) {
  if (name.startsWith('Grand Champion')) return 'Grand Champion';
  if (name.startsWith('Supersonic Legend')) return 'Supersonic Legend';
  return name.split(' ')[0];
}

function buildRankTableFromRanges(rankRanges) {
  return rankRanges.flatMap(([name, divisions]) => {
    const family = getRankFamily(name);
    const style = RANK_STYLE[family];

    if (name === 'Supersonic Legend') {
      const [min, max] = divisions[0];
      return [{ name, short: 'SSL', min, max, icon: style.icon, color: style.color }];
    }

    return divisions.map(([min, max], divIndex) => {
      const shortFamily = family === 'Grand Champion' ? 'GC' : family[0];
      const tier = name.match(/\b(I|II|III)$/)?.[0] || '';
      return {
        name: `${name} Div ${['I', 'II', 'III', 'IV'][divIndex]}`,
        short: `${shortFamily}${tier}.${divIndex + 1}`,
        min,
        max,
        icon: style.icon,
        color: style.color
      };
    });
  });
}

function getRankTable() {
  if (MODE_RANK_RANGES[mode]) return buildRankTableFromRanges(MODE_RANK_RANGES[mode]);
  return buildRankTable(MODE_RANK_STARTS[mode] || MODE_RANK_STARTS['2v2']);
}

const rankBackgroundPlugin = {
  id: 'rankBackground',
  beforeDatasetsDraw(activeChart, _args, pluginOptions) {
    const { ctx: chartCtx, chartArea, scales } = activeChart;
    const yScale = scales?.y;
    if (!chartArea || !yScale || !pluginOptions?.ranks?.length) return;

    const min = yScale.min;
    const max = yScale.max;
    chartCtx.save();
    pluginOptions.ranks.forEach(rank => {
      const from = Math.max(rank.min, min);
      const to = Math.min(rank.max, max);
      if (to < min || from > max) return;

      const yTop = yScale.getPixelForValue(to);
      const yBottom = yScale.getPixelForValue(from);
      const height = Math.max(1, yBottom - yTop);
      chartCtx.fillStyle = hexToRgba(rank.color, 0.18);
      chartCtx.fillRect(chartArea.left, yTop, chartArea.right - chartArea.left, height);

      if (height > 24) {
        chartCtx.fillStyle = hexToRgba(rank.color, 0.78);
        chartCtx.font = '800 12px Inter, sans-serif';
        chartCtx.textAlign = 'right';
        chartCtx.textBaseline = 'middle';
        chartCtx.fillText(`${rank.icon} ${rank.name}`, chartArea.right - 8, yTop + height / 2);
      }
    });
    chartCtx.restore();
  }
};

if (typeof Chart !== 'undefined') {
  Chart.register(rankBackgroundPlugin);
}

function hexToRgba(hex, alpha) {
  const normalized = hex.replace('#', '');
  const value = parseInt(normalized.length === 3
    ? normalized.split('').map(char => char + char).join('')
    : normalized, 16);
  const red = (value >> 16) & 255;
  const green = (value >> 8) & 255;
  const blue = value & 255;
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function getRankForScore(score) {
  const ranks = getRankTable();
  return ranks.find(rank => score >= rank.min && score <= rank.max) || ranks[0];
}

function getVisibleRanks(values) {
  const ranks = getRankTable();
  const rankBands = buildRankBands(ranks);
  if (!values.length) return rankBands.slice(0, 4);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  return rankBands.filter(rank => rank.max >= minValue - 60 && rank.min <= maxValue + 60);
}

function buildRankBands(ranks) {
  const bandMap = new Map();

  ranks.forEach(rank => {
    const baseName = rank.name.replace(/ Div (I|II|III|IV)$/, '');
    const family = getRankFamily(baseName);
    const style = RANK_STYLE[family];
    const current = bandMap.get(baseName);

    if (!current) {
      bandMap.set(baseName, {
        name: baseName,
        short: baseName,
        min: rank.min,
        max: rank.max,
        icon: style.icon,
        color: style.color
      });
      return;
    }

    current.min = Math.min(current.min, rank.min);
    current.max = Math.max(current.max, rank.max);
  });

  return [...bandMap.values()];
}

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
  if (!stored) return [];

  try {
    const parsed = JSON.parse(stored);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    localStorage.removeItem(STORAGE_KEY);
    return [];
  }
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

function compareGamesByDateTime(a, b) {
  return new Date(`${a.date || ''}T${a.time || '00:00'}`) - new Date(`${b.date || ''}T${b.time || '00:00'}`);
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
    games.sort(compareGamesByDateTime);
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
  const currentRank = getRankForScore(realCurrentScore);
  currentScore.innerHTML = `
    <span class="score-value">${realCurrentScore}</span>
    <span class="rank-pill" style="--rank-color:${currentRank.color}">${currentRank.icon} ${currentRank.name}</span>
  `;
  if (winRate) winRate.textContent = `${sessionWinRate.toFixed(1)}%`;
  if (bestWinStreak) bestWinStreak.textContent = String(topWinStreak);
  if (bestLoseStreak) bestLoseStreak.textContent = String(topLoseStreak);
}

function buildChart(games) {
  if (!ctx || typeof Chart === 'undefined') return;

  const sorted = [...games].sort(compareGamesByDateTime);
  const safeMaxGames = sorted.length || CHART_MAX_GAMES;
  const visibleGames = safeMaxGames >= sorted.length
    ? sorted
    : sorted.slice(-safeMaxGames);

  const visibleStartIndex = sorted.length - visibleGames.length;
  const baseScore = getEffectiveBaseScore();
  const deltaValues = visibleGames.map(g => Number(g.points) || 0);
  const labels = visibleGames.map((game, index) => `G${visibleStartIndex + index + 1} - ${game.date}`);
  const values = deltaValues.reduce((acc, points) => {
    const last = acc.length ? acc[acc.length - 1] : baseScore;
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
  const chartValues = packedValues.length ? packedValues : [baseScore];
  const tooltipDeltas = packedValues.length ? packedDeltas : [0];
  const visibleRanks = getVisibleRanks(chartValues);

  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: chartLabels,
      datasets: [{
        label: 'MMR totale',
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
          ticks: {
            color: '#c5d1ff',
            callback(value) {
              const rank = getRankForScore(Number(value));
              return `${value} · ${rank.short}`;
            }
          },
          grid: { color: 'rgba(255,255,255,0.08)' }
        }
      },
      plugins: {
        decimation: {
          enabled: chartValues.length > 120,
          algorithm: 'lttb',
          samples: 120
        },
        rankBackground: { ranks: visibleRanks },
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
              const rank = getRankForScore(totalValue);
              return `MMR: ${totalValue} | Delta: ${signedDelta} | Rank: ${rank.icon} ${rank.name}`;
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
