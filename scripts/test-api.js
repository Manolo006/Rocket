(async () => {
  try {
    const fetch = globalThis.fetch;
    const getResp = await fetch('http://localhost:3000/api/games?mode=1v1');
    console.log('GET status', getResp.status);
    console.log('GET text', await getResp.text());
    const postResp = await fetch('http://localhost:3000/api/games?mode=1v1', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date: '2026-05-23', points: 5 })
    });
    console.log('POST status', postResp.status);
    console.log('POST text', await postResp.text());
  } catch (error) {
    console.error(error);
  }
})();
