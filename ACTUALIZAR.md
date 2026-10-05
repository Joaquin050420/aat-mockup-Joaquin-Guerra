# Actualización semanal (cada martes)

1. Identifica la próxima semana de la NFL y sus eventos:
   `https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/types/2/weeks/{N}/events?limit=50`
2. Por cada evento: fecha, equipos y sede (`/events/{ID}`), y momios actuales y de apertura
   (`/events/{ID}/competitions/{ID}/odds`, primer proveedor). Toma el spread de cada equipo de su propia línea.
3. Lesiones de titulares (Out / Doubtful / Questionable / IR) de cada equipo en
   `https://www.cbssports.com/nfl/teams/{ABR}/{slug}/injuries/`. Solo titulares (`"titular": true`).
4. Fecha del último partido de cada equipo y récords actuales (standings del core API de ESPN).
5. Escribe todo en `data/entrada.json` (mismo formato que ya tiene).
6. Escribe los marcadores finales de la semana anterior en `data/resultados.json`:
   `{"semana": N-1, "resultados": [{"id": "...", "puntos_local": 0, "puntos_visitante": 0}]}`
7. Corre `python3 scripts/actualizar.py` (califica la semana anterior y calcula la nueva).
8. Commit y push a `main`: Vercel publica solo.

Reglas: nunca inventes datos; si algo no se encuentra, déjalo fuera o en null.
