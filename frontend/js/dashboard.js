// =========================================================================
// DASHBOARD.JS — Logique de la page Dashboard
// =========================================================================

let currentYear = 2026;
let pointsChart = null;
let constructorChart = null;
let allResults = [];

// =========================================================================
// INIT
// =========================================================================
document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
});

async function loadDashboard() {
    await Promise.all([
        loadStandings(),
        loadPointsEvolution(),
        loadResults(),
    ]);
    
    // Start countdown if we have races
    startCountdown();
}

// =========================================================================
// COUNTDOWN
// =========================================================================
let countdownInterval;

async function startCountdown() {
    const calendar = await apiFetch('/api/calendar?year=2026');
    if (!calendar || calendar.length === 0) return;
    
    // Find next race
    const now = new Date();
    let nextRace = null;
    
    for (const race of calendar) {
        const raceDate = new Date(race.date);
        // Assuming race is at 15:00 UTC
        raceDate.setUTCHours(15, 0, 0, 0);
        
        if (raceDate > now) {
            nextRace = raceDate;
            break;
        }
    }
    
    if (!nextRace) {
        document.getElementById('countdown').textContent = "Saison Terminée";
        return;
    }
    
    if (countdownInterval) clearInterval(countdownInterval);
    
    const updateTime = () => {
        const diff = nextRace - new Date();
        if (diff <= 0) {
            document.getElementById('countdown').textContent = "C'est parti !";
            clearInterval(countdownInterval);
            return;
        }
        
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        
        document.getElementById('countdown').textContent = `${days}j ${hours.toString().padStart(2, '0')}h ${mins.toString().padStart(2, '0')}m`;
    };
    
    updateTime();
    countdownInterval = setInterval(updateTime, 60000); // update every minute
}

function changeSeason(year) {
    currentYear = year;
    document.querySelectorAll('.season-btn').forEach(btn => {
        btn.classList.toggle('active', parseInt(btn.dataset.year) === year);
    });
    loadDashboard();
}

// =========================================================================
// STANDINGS
// =========================================================================
async function loadStandings() {
    const data = await apiFetch(`/api/standings?year=${currentYear}`);
    if (!data) return;

    // Stat cards
    const drivers = data.drivers;
    const constructors = data.constructors;
    
    if (drivers.length > 0) {
        document.getElementById('stat-leader').textContent = drivers[0].Abbreviation;
        document.getElementById('stat-leader-pts').textContent = `${drivers[0].TotalPoints} pts`;
        document.getElementById('stat-races').textContent = drivers[0].Races;
    }
    if (constructors.length > 0) {
        document.getElementById('stat-team').textContent = constructors[0].TeamName;
        document.getElementById('stat-team-pts').textContent = `${constructors[0].TotalPoints} pts`;
    }

    // Driver standings table
    const driverHTML = `
        <table class="data-table">
            <thead><tr><th>Pos</th><th>Pilote</th><th>Écurie</th><th>Points</th></tr></thead>
            <tbody>
                ${drivers.map((d, i) => `
                    <tr>
                        <td>${positionBadge(i + 1)}</td>
                        <td><strong>${d.Abbreviation}</strong></td>
                        <td><span class="team-color-dot" style="background:${d.TeamColor}"></span>${d.TeamName}</td>
                        <td><strong>${d.TotalPoints}</strong></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>`;
    document.getElementById('driver-standings').innerHTML = driverHTML;

    // Constructor standings (Bar Chart)
    const constContainer = document.getElementById('constructor-chart');
    if (constContainer) {
        if (constructorChart) constructorChart.destroy();
        
        const ctx = constContainer.getContext('2d');
        constructorChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: constructors.map(c => c.TeamName),
                datasets: [{
                    label: 'Points',
                    data: constructors.map(c => c.TotalPoints),
                    backgroundColor: constructors.map(c => c.TeamColor),
                    borderRadius: 4,
                }]
            },
            options: {
                indexAxis: 'y', // horizontal bar chart
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        titleFont: { family: 'Inter' },
                        bodyFont: { family: 'Inter' },
                        padding: 12,
                        cornerRadius: 8
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(128,128,128,0.1)' },
                        ticks: { font: { family: 'Inter', size: 11 } }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { 
                            font: { family: 'Inter', size: 11, weight: '600' },
                            color: '#6E6E73'
                        }
                    }
                }
            }
        });
    }

    // Populate comparison dropdowns
    const options = drivers.map(d => `<option value="${d.Abbreviation}">${d.Abbreviation} (${d.TeamName})</option>`).join('');
    document.getElementById('compare-driver1').innerHTML = options;
    document.getElementById('compare-driver2').innerHTML = options;
    if (drivers.length > 1) {
        document.getElementById('compare-driver2').selectedIndex = 1;
    }
}

// =========================================================================
// POINTS EVOLUTION CHART
// =========================================================================
async function loadPointsEvolution() {
    const data = await apiFetch(`/api/points-evolution?year=${currentYear}`);
    if (!data || !data.labels) return;

    if (pointsChart) pointsChart.destroy();

    const ctx = document.getElementById('points-chart').getContext('2d');
    
    // Top 10 pilotes seulement pour la lisibilité
    const top10 = data.datasets.slice(0, 10);

    pointsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: top10.map(d => ({
                label: d.driver,
                data: d.points,
                borderColor: d.color,
                backgroundColor: d.color + '20',
                borderWidth: 2.5,
                pointRadius: 4,
                pointHoverRadius: 6,
                tension: 0.3,
                fill: false
            }))
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        usePointStyle: true,
                        padding: 16,
                        font: { family: 'Inter', size: 12 }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    titleFont: { family: 'Inter', weight: '600' },
                    bodyFont: { family: 'Inter' },
                    padding: 12,
                    cornerRadius: 8
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { font: { family: 'Inter', size: 11 } }
                },
                y: {
                    grid: { color: 'rgba(128,128,128,0.1)' },
                    ticks: { font: { family: 'Inter', size: 11 } },
                    title: { display: true, text: 'Points', font: { family: 'Inter' } }
                }
            }
        }
    });
}

// Toggle tous les pilotes (afficher / masquer)
function toggleAllDrivers(show) {
    if (!pointsChart) return;
    pointsChart.data.datasets.forEach(dataset => {
        dataset.hidden = !show;
    });
    pointsChart.update();
}

// =========================================================================
// RACE RESULTS
// =========================================================================
async function loadResults() {
    allResults = await apiFetch(`/api/results?year=${currentYear}`);
    if (!allResults || allResults.length === 0) return;

    // Get unique races
    const races = [...new Map(allResults.map(r => [r.RaceNumber, r])).values()];
    
    const selector = document.getElementById('race-selector');
    selector.innerHTML = races.map(r => 
        `<option value="${r.RaceNumber}">Course ${r.RaceNumber} — ${r.EventName}</option>`
    ).join('');
    
    // Show last race by default
    selector.value = races[races.length - 1].RaceNumber;
    
    // Update stat card
    const lastRace = races[races.length - 1];
    document.getElementById('stat-last-race').textContent = lastRace.EventName;
    const lastWinner = allResults.find(r => r.RaceNumber === lastRace.RaceNumber && r.Position === 1);
    if (lastWinner) {
        document.getElementById('stat-last-winner').textContent = `Vainqueur: ${lastWinner.Abbreviation}`;
    }

    loadRaceResults();
}

function loadRaceResults() {
    const raceNum = parseInt(document.getElementById('race-selector').value);
    const raceData = allResults.filter(r => r.RaceNumber === raceNum);
    
    if (raceData.length === 0) return;

    const html = `
        <table class="data-table">
            <thead>
                <tr><th>Pos</th><th>Pilote</th><th>Écurie</th><th>Grille</th><th>+/-</th><th>Points</th><th>Status</th></tr>
            </thead>
            <tbody>
                ${raceData.sort((a, b) => a.Position - b.Position).map(r => {
                    const diff = r.GridPosition - r.Position;
                    const arrow = diff > 0 ? `<span class="arrow-up">↑${diff}</span>` :
                                  diff < 0 ? `<span class="arrow-down">↓${Math.abs(diff)}</span>` :
                                  `<span class="arrow-same">=</span>`;
                    return `
                        <tr>
                            <td>${positionBadge(r.Position)}</td>
                            <td><strong>${r.BroadcastName || r.Abbreviation}</strong></td>
                            <td><span class="team-color-dot" style="background:${r.TeamColor}"></span>${r.TeamName}</td>
                            <td>P${r.GridPosition}</td>
                            <td>${arrow}</td>
                            <td>${r.Points > 0 ? `<strong>+${r.Points}</strong>` : '—'}</td>
                            <td>${(r.Status !== 'Finished' && !r.Status?.includes('Lap')) ? `<span class="badge-dnf">DNF</span> <span style="font-size:11px;color:var(--text-muted);">${r.Status}</span>` : `<span style="color:var(--text-muted)">${r.Status || '—'}</span>`}</td>
                        </tr>`;
                }).join('')}
            </tbody>
        </table>`;
    
    document.getElementById('race-results').innerHTML = html;
}

// =========================================================================
// HEAD TO HEAD COMPARISON
// =========================================================================
async function loadComparison() {
    const d1 = document.getElementById('compare-driver1').value;
    const d2 = document.getElementById('compare-driver2').value;
    
    if (d1 === d2) {
        document.getElementById('comparison-result').innerHTML = '<p style="color:var(--text-muted)">Sélectionne deux pilotes différents.</p>';
        return;
    }

    const data = await apiFetch(`/api/compare?driver1=${d1}&driver2=${d2}&year=${currentYear}`);
    if (!data || !data[d1] || !data[d2]) return;

    const s1 = data[d1];
    const s2 = data[d2];

    const stats = [
        { label: 'Points Totaux', v1: s1.total_points, v2: s2.total_points },
        { label: 'Position Moyenne', v1: s1.avg_position, v2: s2.avg_position, lower: true },
        { label: 'Grille Moyenne', v1: s1.avg_grid, v2: s2.avg_grid, lower: true },
        { label: 'Victoires', v1: s1.wins, v2: s2.wins },
        { label: 'Podiums', v1: s1.podiums, v2: s2.podiums },
        { label: 'Meilleur Résultat', v1: s1.best_finish, v2: s2.best_finish, lower: true },
        { label: 'Abandons', v1: s1.dnfs, v2: s2.dnfs, lower: true },
    ];

    const html = `
        <table class="data-table">
            <thead>
                <tr>
                    <th><span class="team-color-dot" style="background:${s1.color}"></span>${d1}</th>
                    <th style="text-align:center">Statistique</th>
                    <th style="text-align:right"><span class="team-color-dot" style="background:${s2.color}"></span>${d2}</th>
                </tr>
            </thead>
            <tbody>
                ${stats.map(s => {
                    const better1 = s.lower ? s.v1 < s.v2 : s.v1 > s.v2;
                    const better2 = s.lower ? s.v2 < s.v1 : s.v2 > s.v1;
                    return `
                        <tr>
                            <td style="font-weight:${better1 ? '700' : '400'}; color:${better1 ? 'var(--f1-red)' : 'var(--text-primary)'}">${s.v1}</td>
                            <td style="text-align:center; color:var(--text-muted)">${s.label}</td>
                            <td style="text-align:right; font-weight:${better2 ? '700' : '400'}; color:${better2 ? 'var(--f1-red)' : 'var(--text-primary)'}">${s.v2}</td>
                        </tr>`;
                }).join('')}
            </tbody>
        </table>`;
    
    document.getElementById('comparison-result').innerHTML = html;
}
