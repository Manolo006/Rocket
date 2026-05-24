# Personal Game Dashboard

Sito web personale moderno per registrare partite e punti con tre diverse modalità: 1v1, 2v2 e 3v3.

## Funzionalità incluse
- Inserimento partita con data e punti
- Statistiche rapide: partite totali, punti medi
- Grafico lineare dei punti partita per partita
- Tabella con elenco partite e azioni di modifica/eliminazione
- Tre pagine distinte: `index.html` (1v1), `2v2.html`, `3v3.html`
- Persistenza dati in file JSON separati: `data/1v1.json`, `data/2v2.json`, `data/3v3.json`
- Punteggio attuale hardcoded in `public/app.js` per ogni modalità

## Avvio
1. Apri la cartella in un terminale
2. Esegui `npm install`
3. Esegui `npm start`
4. Apri `http://localhost:3000` per 1v1
5. Apri `http://localhost:3000/2v2.html` per 2v2 o `http://localhost:3000/3v3.html` per 3v3

## Personalizzazione del punteggio attuale
- Modifica `public/app.js`
- Aggiorna i valori in `currentScores` per le tre modalità

## Possibili evoluzioni
- sincronizzazione con Google Sheets
- autenticazione personale
- filtri per periodo
- esportazione CSV/Excel
- dashboard avanzata con più grafici
