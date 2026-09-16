# 🚀 Rocket League Auto-Tracker Bot & Companion

Bot automatico in Python per tracciare le partite di Rocket League (vittorie, sconfitte, punti MMR), gestire le sessioni e aggiornare in tempo reale la Dashboard.

---

## ⚡ Avvio Rapido

Fai doppio click sul file:
`
run_bot.bat
`
oppure esegui da terminale:
`ash
python main.py
`

All'avvio comparirà l'interfaccia **Rocket Tracker Companion** (impostata di default Sempre in primo piano).

---

## 🎮 Funzionalità Principali

1. **Rilevamento Automatico dei Match**:
   - **Computer Vision (OpenCV)**: analizza la finestra di Rocket League alla fine della partita per rilevare il banner finale di vittoria o sconfitta.
   - **Log Watcher (Launch.log)**: monitora gli eventi di chiusura partita nei file di log locali del gioco (TAGame\Logs\Launch.log).
   - **Anti-Duplicazione (Debounce)**: cooldown di 35 secondi per evitare registrazioni multiple della stessa partita.

2. **Sincronizzazione Live con la Dashboard**:
   - **Scrittura Diretta su Firebase**: ogni partita viene salvata direttamente nel database Firebase (ocketleaguestatss).
   - **Live SSE Bridge**: la dashboard aperta nel browser (es. 2v2.html) riceve l'evento all'istante e aggiorna la tabella, le statistiche e il grafico Chart.js in diretta senza bisogno di ricaricare con F5.
   - **Indicatore Badge**: nella dashboard compare il badge 🤖 Bot Connesso quando il bot è in esecuzione.

3. **Gestione Intelligente delle Sessioni**:
   - Calcolo automatico di: Partite giocate, Vittorie / Sconfitte, Win Rate %, Bilancio punti netto e Win/Lose Streak.
   - **Auto-Session Timeout**: se non giochi per più di 45 minuti, il bot azzera il bilancio e inizia una nuova sessione automaticamente.
   - Pulsante manuale **Nuova Sessione** per azzerare il bilancio quando vuoi.

4. **Tasti Rapidi (Hotkey Globali)**:
   - **F9**: Registra Vittoria (+9 punti)
   - **F10**: Registra Sconfitta (-9 punti)
   - **F8**: Avvia Nuova Sessione

---

## ⚙️ Configurazione (config.json)

Puoi personalizzare i parametri modificando config.json:
- default_mode: Modalità predefinita (1v1, 2v2 o 3v3).
- win_points e loss_points: Punti MMR assegnati di default (es. +9 / -9).
- uto_session_timeout_minutes: Minuti di inattività prima del reset automatico della sessione (default: 45).
