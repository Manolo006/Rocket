
# Personal Game Dashboard

Versione statica ottimizzata per GitHub Pages con database cloud su Firebase Realtime Database.

## Cosa contiene
- Dashboard `1v1`, `2v2`, `3v3`
- Salvataggio cloud su Firebase Realtime Database (stessi dati su PC/telefono)
- Grafico andamento punteggio con Chart.js
- Modifica, elimina, cancella tutte le partite
- Fallback automatico su `localStorage` se Firebase non è configurato

## Avvio in locale
1. Apri `index.html` nel browser
2. Oppure usa `Live Server` in VS Code

## Setup Firebase (Realtime Database)
1. Crea progetto su [Firebase Console](https://console.firebase.google.com)
2. In `Build > Realtime Database`, crea database (modalità test per iniziare)
3. In `Project settings > General > Your apps`, crea app Web e copia config
4. Apri `firebase-config.js` e imposta campi config (incluso `databaseURL`)
5. Pubblica sito (o apri locale): da quel momento dati sincronizzati tra dispositivi

## Struttura dati Realtime Database
- Path: `modes/{mode}/games/{gameId}`
- Esempio record: `{ date, points, createdAt, updatedAt }`

## Regole Realtime Database minime (test)
Usa regole aperte solo per test iniziale:

```txt
{
  "rules": {
    ".read": true,
    ".write": true
  }
}
```

Poi passa a regole con autenticazione appena possibile.

## Pubblicazione GitHub Pages
1. Push su repository GitHub
2. Abilita GitHub Pages da branch `main` (o `gh-pages`)
3. Verifica `index.html` in root

## Personalizzazioni
- Aggiorna `currentScores` in `app.js`
- Modifica testi in `index.html`, `2v2.html`, `3v3.html`
- Cambia stile in `style.css`
