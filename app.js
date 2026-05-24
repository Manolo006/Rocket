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
const totalGames = document.getElementById('totalGames');
const averagePoints = document.getElementById('averagePoints');
const currentScore = document.getElementById('currentScore');
const formMessage = document.getElementById('formMessage');
const clearAll = document.getElementById('clearAll');
const ctx = document.getElementById('pointsChart').getContext('2d');
let chart;
let editingId = null;
let firestore = null;

const STORAGE_KEY = `games_${mode}`;

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

function initFirebase() {
  if (!hasFirebase) return;
  if (!firebase.apps.length) {
    firebase.initializeApp(FIREBASE_CONFIG);
  }
  firestore = firebase.firestore();
}

async function getSavedGames() {
  if (!firestore) {
    return getLocalSavedGames();
  }

  try {
    const snapshot = await firestore
      .collection('modes')
      .doc(mode)
      .collection('games')
      .orderBy('date', 'asc')
      .get();

    return snapshot.docs.map(doc => {
      const data = doc.data();
      return {
        id: doc.id,
        date: data.date || '',
        points: Number(data.points) || 0
      };
    });
  } catch (error) {
    showMessage('Firebase non risponde, uso localStorage.', true);
    return getLocalSavedGames();
  }
}

async function addGame(game) {
  if (firestore) {
    await firestore
      .collection('modes')
      .doc(mode)
      .collection('games')
      .add({
        date: game.date,
        points: Number(game.points) || 0,
        createdAt: firebase.firestore.FieldValue.serverTimestamp()
      });
    return;
  }
  const games = getLocalSavedGames();
  const nextId = games.length ? Math.max(...games.map(g => g.id)) + 1 : 1;
  games.push({ id: nextId, ...game });
  persistLocalGames(games);
}

async function updateGame(id, newData) {
  if (firestore) {
    await firestore
      .collection('modes')
      .doc(mode)
      .collection('games')
      .doc(String(id))
      .update({
        date: newData.date,
        points: Number(newData.points) || 0,
        updatedAt: firebase.firestore.FieldValue.serverTimestamp()
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
  if (firestore) {
    await firestore
      .collection('modes')
      .doc(mode)
      .collection('games')
      .doc(String(id))
      .delete();
    return;
  }
  const games = getLocalSavedGames().filter(g => g.id !== id);
  persistLocalGames(games);
}

async function clearAllGames() {
  if (firestore) {
    const snapshot = await firestore
      .collection('modes')
      .doc(mode)
      .collection('games')
      .get();
    const batch = firestore.batch();
    snapshot.forEach(doc => batch.delete(doc.ref));
    await batch.commit();
    return;
  }
  localStorage.removeItem(STORAGE_KEY);
}

function buildRow(game) {
  const row = document.createElement('tr');
  row.innerHTML = `
    <td>${game.date}</td>
    <td>${game.points}</td>
    <td>
      <button class="action-button edit" data-id="${String(game.id)}">Modifica</button>
      <button class="action-button delete" data-id="${String(game.id)}">Elimina</button>
    </td>
  `;
  return row;
}

function updateStats(games) {
  const total = games.length;
  const points = games.map(g => Number(g.points) || 0);
  const average = total ? Math.round(points.reduce((sum, value) => sum + value, 0) / total) : 0;
  totalGames.textContent = total;
  averagePoints.textContent = average;
  currentScore.textContent = currentScores[mode] ?? 0;
}

function buildChart(games) {
  const sorted = [...games].sort((a, b) => new Date(a.date) - new Date(b.date));
  const deltaValues = sorted.map(g => Number(g.points) || 0);
  const currentTotal = currentScores[mode] ?? 0;
  const startingTotal = currentTotal - deltaValues.reduce((sum, value) => sum + value, 0);
  const labels = sorted.map((game, index) => `G${index + 1} - ${game.date}`);
  const values = deltaValues.reduce((acc, points) => {
    const last = acc.length ? acc[acc.length - 1] : startingTotal;
    acc.push(last + points);
    return acc;
  }, []);
  const chartLabels = values.length ? labels : ['Totale attuale'];
  const chartValues = values.length ? values : [currentTotal];

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
        pointRadius: 5,
        pointHoverRadius: 7
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          ticks: { color: '#c5d1ff', maxRotation: 40, minRotation: 0 },
          grid: { color: 'rgba(255,255,255,0.06)' }
        },
        y: {
          beginAtZero: false,
          ticks: { color: '#c5d1ff' },
          grid: { color: 'rgba(255,255,255,0.08)' }
        }
      },
      plugins: {
        legend: { labels: { color: '#d2d9ff' } },
        tooltip: { mode: 'index', intersect: false }
      }
    }
  });
}

async function refresh() {
  const games = await getSavedGames();
  gameList.innerHTML = '';
  games.forEach(game => gameList.appendChild(buildRow(game)));
  updateStats(games);
  buildChart(games);
}

gameForm.addEventListener('submit', async event => {
  event.preventDefault();
  const dateValue = document.getElementById('date').value;
  const pointsValue = Number(document.getElementById('points').value);
  if (!dateValue || Number.isNaN(pointsValue)) {
    showMessage('Inserisci data e punteggio validi.');
    return;
  }

  try {
    if (editingId) {
      await updateGame(editingId, { date: dateValue, points: pointsValue });
      showMessage('Partita aggiornata con successo.', false);
      editingId = null;
    } else {
      await addGame({ date: dateValue, points: pointsValue });
      showMessage('Partita salvata con successo.', false);
    }
    gameForm.reset();
    refresh();
  } catch (error) {
    showMessage(error.message || 'Errore durante il salvataggio.');
  }
});

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
    document.getElementById('points').value = game.points;
    editingId = firestore ? id : (Number.isNaN(localId) ? id : localId);
  }

  if (button.classList.contains('delete')) {
    try {
      await deleteGame(firestore ? id : (Number.isNaN(localId) ? id : localId));
      showMessage('Partita eliminata.', false);
      refresh();
    } catch (error) {
      showMessage(error.message || 'Errore durante l’eliminazione.');
    }
  }
});

initFirebase();

clearAll.addEventListener('click', async () => {
  try {
    await clearAllGames();
    editingId = null;
    gameForm.reset();
    refresh();
    showMessage('Tutte le partite sono state cancellate.', false);
  } catch (error) {
    showMessage(error.message || 'Errore durante il reset.');
  }
});

refresh();
