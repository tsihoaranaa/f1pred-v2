// =========================================================================
// PERSO.JS — Logique de la page Espace Personnel
// =========================================================================

let accuracyChart = null;

document.addEventListener('DOMContentLoaded', () => {
    loadPerso();
});

async function loadPerso() {
    await Promise.all([
        loadAccuracy(),
        loadHistory()
    ]);
}

// =========================================================================
// ACCURACY
// =========================================================================
async function loadAccuracy() {
    const data = await apiFetch('/api/accuracy');
    if (!data) return;

    // Stat cards
    if (data.global_mae !== null) {
        document.getElementById('stat-mae').textContent = data.global_mae;
    }

    if (data.per_race && data.per_race.length > 0) {
        document.getElementById('stat-pred-count').textContent = data.per_race.length;
        
        const best = data.per_race.reduce((a, b) => a.mae < b.mae ? a : b);
        document.getElementById('stat-best-mae').textContent = best.mae;
        document.getElementById('stat-best-race').textContent = best.race_name;

        // Chart
        renderAccuracyChart(data.per_race);
    }
}

function renderAccuracyChart(perRace) {
    if (accuracyChart) accuracyChart.destroy();

    const ctx = document.getElementById('accuracy-chart').getContext('2d');
    
    accuracyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: perRace.map(r => r.race_name),
            datasets: [{
                label: 'MAE (positions)',
                data: perRace.map(r => r.mae),
                backgroundColor: perRace.map(r => r.mae < 3 ? '#34C759' : r.mae < 5 ? '#FF9500' : '#E10600'),
                borderRadius: 6,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    titleFont: { family: 'Inter' },
                    bodyFont: { family: 'Inter' },
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: {
                        label: ctx => `${ctx.parsed.y} positions d'écart`
                    }
                }
            },
            scales: {
                x: { grid: { display: false }, ticks: { font: { family: 'Inter', size: 11 } } },
                y: { 
                    grid: { color: 'rgba(128,128,128,0.1)' },
                    ticks: { font: { family: 'Inter', size: 11 } },
                    title: { display: true, text: 'MAE (positions)', font: { family: 'Inter' } }
                }
            }
        }
    });
}

// =========================================================================
// PREDICTION HISTORY
// =========================================================================
async function loadHistory() {
    const data = await apiFetch('/api/prediction-history');
    
    if (!data || data.length === 0) {
        document.getElementById('prediction-history').innerHTML = `
            <div style="text-align:center; padding:40px; color:var(--text-muted);">
                <p style="font-size:36px; margin-bottom:12px;">🔮</p>
                <p>Aucune prédiction sauvegardée.</p>
                <p style="font-size:13px; margin-top:8px;">Va dans l'onglet <strong>Prédiction</strong> pour en créer une !</p>
            </div>`;
        return;
    }

    const html = `
        <table class="data-table">
            <thead>
                <tr><th>Course</th><th>Date</th><th>Top 3 Prédit</th></tr>
            </thead>
            <tbody>
                ${data.map(p => {
                    let results = [];
                    try { results = JSON.parse(p.prediction_data); } catch(e) {}
                    const top3 = results.slice(0, 3).map(r => r.Abbreviation || r.driver || '?').join(', ');
                    const date = new Date(p.created_at).toLocaleDateString('fr-FR');
                    return `
                        <tr>
                            <td><strong>${p.race_name || 'Course'}</strong></td>
                            <td style="color:var(--text-muted)">${date}</td>
                            <td>🥇🥈🥉 ${top3}</td>
                        </tr>`;
                }).join('')}
            </tbody>
        </table>`;

    document.getElementById('prediction-history').innerHTML = html;
}
