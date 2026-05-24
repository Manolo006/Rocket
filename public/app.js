const mode = document.body.dataset.mode || '1v1';
const apiBaseUrl = `/api/games/${mode}`;
const currentScores = {
  '1v1': 169,
  '2v2': 274,
  '3v3': 442
};

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

function showMessage(text, isError = true) {
  if (!formMessage) return;
  formMessage.textContent = text;
  formMessage.style.color = isError ? '#ffb3b3' : '#b9ffd6';
}

function apiRecordUrl(id) {
  return id ? `/api/games/${mode}/${id}` : apiBaseUrl;
}

async function fetchGames() {
  const response = await fetch(apiBaseUrl);
  return response.ok ? response.json() : [];
}

async function saveGame(data) {
  const method = editingId ? 'PUT' : 'POST';
  const url = editingId ? apiRecordUrl(editingId) : apiRecordUrl();
  const response = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || 'Impossibile salvare la partita.');
  }
  return response.json();
}

async function deleteGame(id) {
  await fetch(apiRecordUrl(id), { method: 'DELETE' });
}

function buildRow(game) {
  const row = document.createElement('tr');
  row.innerHTML = `
    <td>${game.date}</td>
    <td>${game.points}</td>
    <td>
      <button class="action-button edit" data-id="${game.id}">Modifica</button>
      <button class="action-button delete" data-id="${game.id}">Elimina</button>
    </td>
  `;
  return row;
}

function updateStats(games) {
  const total = games.length;
  const points = games.map(g => Number(g.points) || 0);
  const average = total ? Math.round(points.reduce((sum, v) => sum + v, 0) / total) : 0;
  totalGames.textContent = total;
  averagePoints.textContent = average;
  currentScore.textContent = currentScores[mode] ?? 0;
}

function buildChart(games) {
  const sorted = [...games].sort((a, b) => new Date(a.date) - new Date(b.date));
  const deltaValues = sorted.map(g => Number(g.points) || 0);
  const currentTotal = currentScores[mode] ?? 0;
  const startingTotal = currentTotal - deltaValues.reduce((sum, value) => sum + value, 0);
  const labels = sorted.map((g, index) => `G${index + 1} - ${g.date}`);
  const totalValues = [];
  let runningTotal = startingTotal;
  for (const delta of deltaValues) {
    runningTotal += delta;
    totalValues.push(runningTotal);
  }
  const values = totalValues.length ? totalValues : [currentTotal];
  const finalLabels = totalValues.length ? labels : ['Totale attuale'];
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: finalLabels,
      datasets: [{
        label: 'Punteggio totale',
        data: values,
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
  const games = await fetchGames();
  gameList.innerHTML = '';
  games.forEach(game => gameList.appendChild(buildRow(game)));
  updateStats(games);
  buildChart(games);
}

gameForm.addEventListener('submit', async event => {
  event.preventDefault();
  showMessage('Sto salvando...', false);
  const dateValue = document.getElementById('date').value;
  const pointsValue = Number(document.getElementById('points').value);
  if (!dateValue || Number.isNaN(pointsValue)) {
    showMessage('Inserisci data e punteggio validi.');
    return;
  }
  try {
    await saveGame({ date: dateValue, points: pointsValue });
    gameForm.reset();
    editingId = null;
    showMessage('Partita salvata con successo.', false);
    refresh();
  } catch (error) {
    showMessage(error.message || 'Errore durante il salvataggio.');
    console.error('Save error:', error);
  }
});

gameList.addEventListener('click', async event => {
  const button = event.target.closest('button');
  if (!button) return;
  const id = button.dataset.id;
  if (button.classList.contains('edit')) {
    const games = await fetchGames();
    const game = games.find(g => g.id === Number(id));
    if (!game) return;
    document.getElementById('date').value = game.date;
    document.getElementById('points').value = game.points;
    editingId = Number(id);
  }
  if (button.classList.contains('delete')) {
    await deleteGame(id);
    refresh();
  }
});

clearAll.addEventListener('click', async () => {
  const games = await fetchGames();
  for (const game of games) {
    await deleteGame(game.id);
  }
  refresh();
});

refresh();
