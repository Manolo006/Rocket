const express = require('express');
const fs = require('fs');
const path = require('path');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3000;
const allowedModes = ['1v1', '2v2', '3v3'];

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

function resolveMode(mode) {
  return allowedModes.includes(mode) ? mode : '1v1';
}

function dataFile(mode) {
  return path.join(__dirname, 'data', `${mode}.json`);
}

function readGames(mode) {
  const filePath = dataFile(mode);
  if (!fs.existsSync(filePath)) return [];
  const raw = fs.readFileSync(filePath, 'utf8');
  try {
    return JSON.parse(raw) || [];
  } catch (error) {
    return [];
  }
}

function writeGames(mode, games) {
  fs.writeFileSync(dataFile(mode), JSON.stringify(games, null, 2));
}

app.get('/api/games/:mode', (req, res) => {
  const mode = resolveMode(req.params.mode);
  res.json(readGames(mode));
});

app.post('/api/games/:mode', (req, res) => {
  const mode = resolveMode(req.params.mode);
  const games = readGames(mode);
  const nextId = games.length ? Math.max(...games.map(g => g.id)) + 1 : 1;
  const record = {
    id: nextId,
    date: req.body.date || new Date().toISOString().split('T')[0],
    points: typeof req.body.points === 'number' ? req.body.points : 0
  };
  games.push(record);
  writeGames(mode, games);
  res.status(201).json(record);
});

app.put('/api/games/:mode/:id', (req, res) => {
  const mode = resolveMode(req.params.mode);
  const games = readGames(mode);
  const id = Number(req.params.id);
  const index = games.findIndex(g => g.id === id);
  if (index === -1) return res.status(404).json({ error: 'Record non trovato' });
  games[index] = {
    ...games[index],
    date: req.body.date || games[index].date,
    points: typeof req.body.points === 'number' ? req.body.points : games[index].points
  };
  writeGames(mode, games);
  res.json(games[index]);
});

app.delete('/api/games/:mode/:id', (req, res) => {
  const mode = resolveMode(req.params.mode);
  const games = readGames(mode);
  const id = Number(req.params.id);
  const filtered = games.filter(g => g.id !== id);
  if (filtered.length === games.length) return res.status(404).json({ error: 'Record non trovato' });
  writeGames(mode, filtered);
  res.json({ success: true });
});

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Server in ascolto su http://localhost:${PORT}`);
});
