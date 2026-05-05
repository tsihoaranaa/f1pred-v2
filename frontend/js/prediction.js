// =========================================================================
// PREDICTION.JS — Logique de la page Prédiction
// =========================================================================

let driversList = [];
let lastPrediction = null;

document.addEventListener('DOMContentLoaded', () => {
    loadDrivers();
});

// =========================================================================
// LOAD DRIVERS & BUILD GRID
// =========================================================================
async function loadDrivers() {
    driversList = await apiFetch('/api/drivers?year=2026');
    if (!driversList) return;
    
    buildGridInputs();
}

function buildGridInputs() {
    const container = document.getElementById('grid-inputs');
    
    container.innerHTML = driversList.map((d, i) => `
        <div style="display:flex; align-items:center; gap:10px; padding:6px 0; border-bottom:1px solid var(--border-color);">
            <span style="width:30px; font-size:12px; color:var(--text-muted); font-weight:600;">P${i + 1}</span>
            <span class="team-color-dot" style="background:${d.TeamColor}"></span>
            <span style="flex:1; font-size:14px; font-weight:500;">${d.Abbreviation}</span>
            <input type="number" class="form-input grid-pos-input" 
                   data-driver="${d.Abbreviation}" 
                   value="${i + 1}" min="1" max="${driversList.length}"
                   style="width:60px; text-align:center; padding:6px;">
        </div>
    `).join('');
}

function autoGrid() {
    // Reset to default order
    document.querySelectorAll('.grid-pos-input').forEach((input, i) => {
        input.value = i + 1;
    });
}

function getGridData() {
    const grid = {};
    document.querySelectorAll('.grid-pos-input').forEach(input => {
        grid[input.dataset.driver] = parseInt(input.value);
    });
    return grid;
}

function getWeatherData() {
    return {
        air_temp: parseFloat(document.getElementById('air-temp').value),
        track_temp: parseFloat(document.getElementById('track-temp').value),
        humidity: parseFloat(document.getElementById('humidity').value),
        wind_speed: parseFloat(document.getElementById('wind-speed').value),
        rainfall: document.getElementById('rainfall').checked ? 1 : 0
    };
}

// =========================================================================
// RUN PREDICTION (XGBoost)
// =========================================================================
async function runPrediction() {
    const btn = document.getElementById('btn-predict');
    btn.innerHTML = '⏳ Calcul en cours...';
    btn.disabled = true;

    const data = await apiFetch('/api/predict', {
        method: 'POST',
        body: JSON.stringify({
            grid: getGridData(),
            weather: getWeatherData()
        })
    });

    btn.innerHTML = '🏁 Lancer la Prédiction';
    btn.disabled = false;

    if (!data) return;

    lastPrediction = data;
    const card = document.getElementById('prediction-card');
    card.style.display = 'block';

    const html = `
        <table class="data-table">
            <thead><tr><th>Pos</th><th>Pilote</th><th>Écurie</th><th>Grille</th><th>+/-</th><th>Pts</th></tr></thead>
            <tbody>
                ${data.map(r => {
                    const diff = r.GridPosition - r.position;
                    const arrow = diff > 0 ? `<span class="arrow-up">↑${diff}</span>` :
                                  diff < 0 ? `<span class="arrow-down">↓${Math.abs(diff)}</span>` :
                                  `<span class="arrow-same">=</span>`;
                    return `
                        <tr>
                            <td>${positionBadge(r.position)}</td>
                            <td><strong>${r.Abbreviation}</strong></td>
                            <td><span class="team-color-dot" style="background:${r.color}"></span>${r.TeamName}</td>
                            <td>P${r.GridPosition}</td>
                            <td>${arrow}</td>
                            <td>${r.points > 0 ? `<strong>+${r.points}</strong>` : '—'}</td>
                        </tr>`;
                }).join('')}
            </tbody>
        </table>`;
    
    document.getElementById('prediction-result').innerHTML = html;
}

// =========================================================================
// RUN MONTE CARLO
// =========================================================================
async function runMonteCarlo() {
    const btn = document.getElementById('btn-monte-carlo');
    btn.innerHTML = '⏳ 3000 simulations...';
    btn.disabled = true;

    const data = await apiFetch('/api/monte-carlo?n_simulations=3000', {
        method: 'POST',
        body: JSON.stringify({
            grid: getGridData(),
            weather: getWeatherData()
        })
    });

    btn.innerHTML = '🎲 Simulation Monte Carlo';
    btn.disabled = false;

    if (!data) return;

    const card = document.getElementById('monte-carlo-card');
    card.style.display = 'block';

    const html = `
        <table class="data-table">
            <thead>
                <tr><th>Pilote</th><th>🏆 Victoire</th><th>🏅 Podium</th><th>Top 5</th><th>Points</th><th>Pos Moy</th></tr>
            </thead>
            <tbody>
                ${data.map(r => `
                    <tr>
                        <td>
                            <span class="team-color-dot" style="background:${r.color}"></span>
                            <strong>${r.driver}</strong>
                        </td>
                        <td>
                            <div style="display:flex;align-items:center;gap:8px;">
                                <div style="width:80px;height:6px;background:var(--border-color);border-radius:3px;">
                                    <div style="width:${r.win_pct}%;height:100%;background:var(--f1-red);border-radius:3px;"></div>
                                </div>
                                <span style="font-weight:600;font-size:13px;">${r.win_pct}%</span>
                            </div>
                        </td>
                        <td>${r.podium_pct}%</td>
                        <td>${r.top5_pct}%</td>
                        <td>${r.points_pct}%</td>
                        <td>P${r.avg_position}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>`;
    
    document.getElementById('monte-carlo-result').innerHTML = html;
}

// =========================================================================
// SAVE PREDICTION
// =========================================================================
async function savePrediction() {
    if (!lastPrediction) return;

    const result = await apiFetch('/api/save-prediction', {
        method: 'POST',
        body: JSON.stringify({
            race_name: 'Prochaine Course',
            year: 2026,
            race_number: 0,
            results: lastPrediction
        })
    });

    if (result?.status === 'ok') {
        showToast('Prédiction sauvegardée !', 'success');
    }
}
