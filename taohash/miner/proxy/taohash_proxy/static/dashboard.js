// Global state for tracking hashrate history
let hashrateHistory = {
  labels: [],
  datasets: []
};

// Global chart instances
let hashrateChart = null;
let shareChart = null;

// Constants
const REFRESH_INTERVAL = 10000; // 10 seconds
const MAX_HISTORY_POINTS = 20;
const COLORS = [
  '#4ECDC4', '#52D9D0', '#6AE4DB', '#82EFE6', '#9AF9F1', 
  '#FFE66D', '#FF6B6B', '#C9ADA7', '#B8C5D6', '#7A8CA0'
];

// Initialize the dashboard
document.addEventListener('DOMContentLoaded', function() {
  // Set Chart.js defaults
  Chart.defaults.color = '#B8C5D6';
  Chart.defaults.borderColor = 'rgba(78, 205, 196, 0.15)';
  Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, sans-serif";
  
  initCharts();
  updateData();
  
  // Set up refresh interval
  setInterval(updateData, REFRESH_INTERVAL);
});

// Initialize Chart.js charts
function initCharts() {
  // Hashrate chart
  const hashrateCtx = document.getElementById('hashrateChart').getContext('2d');
  hashrateChart = new Chart(hashrateCtx, {
    type: 'line',
    data: {
      labels: [],
      datasets: []
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 1000
      },
      scales: {
        x: {
          grid: {
            color: 'rgba(78, 205, 196, 0.05)',
            borderColor: 'rgba(78, 205, 196, 0.15)'
          },
          ticks: {
            color: '#B8C5D6'
          }
        },
        y: {
          beginAtZero: true,
          grid: {
            color: 'rgba(78, 205, 196, 0.05)',
            borderColor: 'rgba(78, 205, 196, 0.15)'
          },
          ticks: {
            color: '#B8C5D6'
          },
          title: {
            display: true,
            text: 'Hashrate',
            color: '#B8C5D6'
          }
        }
      },
      plugins: {
        legend: {
          position: 'top',
          labels: {
            color: '#B8C5D6',
            usePointStyle: true,
            padding: 20
          }
        },
        tooltip: {
          backgroundColor: 'rgba(22, 34, 54, 0.95)',
          titleColor: '#FFFFFF',
          bodyColor: '#B8C5D6',
          borderColor: 'rgba(78, 205, 196, 0.3)',
          borderWidth: 1,
          padding: 12,
          callbacks: {
            label: function(context) {
              let label = context.dataset.label || '';
              if (label) {
                label += ': ';
              }
              if (context.parsed.y !== null) {
                label += formatHashrate(context.parsed.y);
              }
              return label;
            }
          }
        }
      }
    }
  });
  
  // Shares chart
  const sharesCtx = document.getElementById('sharesChart').getContext('2d');
  shareChart = new Chart(sharesCtx, {
    type: 'doughnut',
    data: {
      labels: ['Accepted', 'Rejected'],
      datasets: [{
        data: [0, 0],
        backgroundColor: [
          'rgba(78, 205, 196, 0.8)',
          'rgba(255, 107, 107, 0.8)'
        ],
        borderColor: [
          '#4ECDC4',
          '#FF6B6B'
        ],
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 1000
      },
      cutout: '70%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: '#B8C5D6',
            usePointStyle: true,
            padding: 15
          }
        },
        tooltip: {
          backgroundColor: 'rgba(22, 34, 54, 0.95)',
          titleColor: '#FFFFFF',
          bodyColor: '#B8C5D6',
          borderColor: 'rgba(78, 205, 196, 0.3)',
          borderWidth: 1,
          padding: 12
        }
      }
    }
  });
}

// Fetch data from API and update dashboard
async function updateData() {
  try {
    // Fetch miners stats
    const statsResponse = await fetch('/api/stats');
    const minerStats = await statsResponse.json();
    
    if (!minerStats || !Array.isArray(minerStats)) {
      console.error('Invalid miners data format:', minerStats);
      return;
    }
    
    const poolsResponse = await fetch('/api/pools');
    const poolsInfo = await poolsResponse.json();
    
    // Update last refresh time
    document.getElementById('lastRefreshed').textContent = new Date().toLocaleTimeString();
    
    // Update pools display
    updatePoolsDisplay(poolsInfo);
    
    // Calculate summary statistics
    updateSummaryStats(minerStats);
    
    // Add new data point to hashrate history
    addHashrateDataPoint(minerStats);
    
    // Update shares chart
    updateSharesChart(minerStats);
    
    // Update miners table
    updateMinersTable(minerStats);
    
  } catch (error) {
    console.error('Error fetching stats:', error);
  }
}

// Update pools display with cards
function updatePoolsDisplay(poolsData) {
  const container = document.getElementById('poolsContainer');
  container.innerHTML = '';
  
  // Create a card for each pool
  for (const [poolName, poolData] of Object.entries(poolsData)) {
    const card = document.createElement('div');
    card.className = 'pool-card';
    
    const isActive = poolData.connected_miners > 0;
    
    card.innerHTML = `
      <div class="pool-header">
        <h3>${poolName.toUpperCase()}</h3>
        <span class="pool-status ${isActive ? 'active' : 'inactive'}">
          ${isActive ? 'Active' : 'Idle'}
        </span>
      </div>
      <div class="pool-details">
        <div class="pool-detail">
          <span class="detail-label">Address:</span>
          <span class="detail-value">${poolData.host}</span>
        </div>
        <div class="pool-detail">
          <span class="detail-label">Port:</span>
          <span class="detail-value">${poolData.port}</span>
        </div>
        <div class="pool-detail">
          <span class="detail-label">User:</span>
          <span class="detail-value">${poolData.user}</span>
        </div>
        <div class="pool-stats">
          <div class="pool-stat">
            <span class="stat-value">${poolData.connected_miners}</span>
            <span class="stat-label">Miners</span>
          </div>
          <div class="pool-stat">
            <span class="stat-value">${formatHashrate(poolData.total_hashrate)}</span>
            <span class="stat-label">Hashrate</span>
          </div>
          <div class="pool-stat">
            <span class="stat-value">${poolData.total_accepted}</span>
            <span class="stat-label">Accepted</span>
          </div>
        </div>
      </div>
    `;
    
    container.appendChild(card);
  }
}

// Update summary statistics cards
function updateSummaryStats(data) {
  // Calculate total hashrate
  const totalHashrate = data.reduce((sum, miner) => sum + miner.hashrate, 0);
  document.getElementById('totalHashrate').textContent = formatHashrate(totalHashrate);
  
  // Calculate total miners
  document.getElementById('activeMiners').textContent = data.length;
  
  // Calculate total shares
  const totalAccepted = data.reduce((sum, miner) => sum + miner.accepted, 0);
  const totalRejected = data.reduce((sum, miner) => sum + miner.rejected, 0);
  document.getElementById('totalShares').textContent = totalAccepted + totalRejected;
  
  // Calculate acceptance rate
  const acceptanceRate = totalAccepted + totalRejected === 0 ? 
    100 : (totalAccepted / (totalAccepted + totalRejected) * 100).toFixed(2);
  document.getElementById('acceptanceRate').textContent = acceptanceRate + '%';
}

// Add new data point to hashrate history
function addHashrateDataPoint(data) {
  // Add new timestamp
  const now = new Date();
  const timeString = now.getHours().toString().padStart(2, '0') + ':' +
                     now.getMinutes().toString().padStart(2, '0') + ':' +
                     now.getSeconds().toString().padStart(2, '0');
  
  // If we have too many points, remove the oldest
  if (hashrateHistory.labels.length >= MAX_HISTORY_POINTS) {
    hashrateHistory.labels.shift();
    hashrateHistory.datasets.forEach(dataset => dataset.data.shift());
  }
  
  // Add new label
  hashrateHistory.labels.push(timeString);
  
  // Aggregate miners for graph display
  const aggregatedData = {};
  data.forEach(miner => {
    const label = miner.worker || miner.miner;
    if (aggregatedData[label]) {
      // Sum hashrates for miners with same worker name
      aggregatedData[label].hashrate += miner.hashrate;
    } else {
      aggregatedData[label] = {
        ...miner,
        hashrate: miner.hashrate
      };
    }
  });
  
  const graphData = Object.values(aggregatedData);
  
  graphData.forEach((miner, index) => {
    const label = miner.worker || miner.miner;
    const existingDataset = hashrateHistory.datasets.find(d => d.label === label);
    
    if (existingDataset) {
      // Update existing dataset
      existingDataset.data.push(miner.hashrate);
    } else {
      // Create new dataset
      const color = COLORS[index % COLORS.length];
      const newDataset = {
        label: label,
        data: Array(hashrateHistory.labels.length - 1).fill(0).concat([miner.hashrate]),
        borderColor: color,
        backgroundColor: color + '20',
        tension: 0.4,
        fill: false,
        pointRadius: 2,
        borderWidth: 2
      };
      hashrateHistory.datasets.push(newDataset);
    }
  });
  
  // Remove datasets for miners that are no longer connected
  const activeLabels = Object.keys(aggregatedData);
  hashrateHistory.datasets = hashrateHistory.datasets.filter(ds => 
    activeLabels.includes(ds.label));
  
  // Update chart
  hashrateChart.data.labels = hashrateHistory.labels;
  hashrateChart.data.datasets = hashrateHistory.datasets;
  hashrateChart.update();
}

// Update shares chart
function updateSharesChart(data) {
  const totalAccepted = data.reduce((sum, miner) => sum + miner.accepted, 0);
  const totalRejected = data.reduce((sum, miner) => sum + miner.rejected, 0);
  
  shareChart.data.datasets[0].data = [totalAccepted, totalRejected];
  shareChart.update();
}

// Update miners table
function updateMinersTable(data) {
  const tbody = document.getElementById('minersTable').querySelector('tbody');
  tbody.innerHTML = '';
  
  data.forEach(miner => {
    const row = document.createElement('tr');
    
    // Miner address
    const minerCell = document.createElement('td');
    minerCell.textContent = miner.miner;
    row.appendChild(minerCell);
    
    // Worker name
    const workerCell = document.createElement('td');
    workerCell.textContent = miner.worker || '-';
    row.appendChild(workerCell);
    
    // Pool Type
    const poolTypeCell = document.createElement('td');
    const poolTypeBadge = document.createElement('span');
    poolTypeBadge.classList.add('badge');
    poolTypeBadge.textContent = miner.pool_type || 'UNKNOWN';
    if (miner.pool_type === 'HIGH_DIFF') {
      poolTypeBadge.style.backgroundColor = 'rgba(255, 107, 107, 0.2)';
      poolTypeBadge.style.color = '#FF6B6B';
    } else if (miner.pool_type === 'NORMAL') {
      poolTypeBadge.style.backgroundColor = 'rgba(78, 205, 196, 0.2)';
      poolTypeBadge.style.color = '#4ECDC4';
    } else {
      poolTypeBadge.style.backgroundColor = 'rgba(184, 197, 214, 0.2)';
      poolTypeBadge.style.color = '#B8C5D6';
    }
    poolTypeCell.appendChild(poolTypeBadge);
    row.appendChild(poolTypeCell);
    
    // Hashrate
    const hashrateCell = document.createElement('td');
    hashrateCell.textContent = formatHashrate(miner.hashrate);
    row.appendChild(hashrateCell);
    
    // Accepted shares
    const acceptedCell = document.createElement('td');
    acceptedCell.textContent = miner.accepted;
    row.appendChild(acceptedCell);
    
    // Rejected shares
    const rejectedCell = document.createElement('td');
    rejectedCell.textContent = miner.rejected;
    row.appendChild(rejectedCell);
    
    // Acceptance rate
    const rateCell = document.createElement('td');
    const rate = miner.accepted + miner.rejected === 0 ? 
      100 : (miner.accepted / (miner.accepted + miner.rejected) * 100).toFixed(2);
    
    const badge = document.createElement('span');
    badge.classList.add('badge');
    badge.classList.add(rate >= 95 ? 'badge-success' : 'badge-danger');
    badge.textContent = rate + '%';
    
    rateCell.appendChild(badge);
    row.appendChild(rateCell);
    
    // Pool Difficulty
    const poolDiffCell = document.createElement('td');
    poolDiffCell.textContent = (miner.pool_difficulty || miner.difficulty).toFixed(2);
    row.appendChild(poolDiffCell);
    
    // Miner Difficulty (effective)
    const minerDiffCell = document.createElement('td');
    minerDiffCell.textContent = miner.difficulty.toFixed(2);
    // Highlight if different from pool difficulty
    if (miner.pool_difficulty && miner.pool_difficulty !== miner.difficulty) {
      minerDiffCell.style.color = '#4ECDC4';
      minerDiffCell.style.fontWeight = '500';
    }
    row.appendChild(minerDiffCell);
    
    tbody.appendChild(row);
  });
}

// Helper function to format hashrate
function formatHashrate(hashrate) {
  if (hashrate >= 1e18) {
    return (hashrate / 1e18).toFixed(2) + ' EH/s';
  } else if (hashrate >= 1e15) {
    return (hashrate / 1e15).toFixed(2) + ' PH/s';
  } else if (hashrate >= 1e12) {
    return (hashrate / 1e12).toFixed(2) + ' TH/s';
  } else if (hashrate >= 1e9) {
    return (hashrate / 1e9).toFixed(2) + ' GH/s';
  } else if (hashrate >= 1e6) {
    return (hashrate / 1e6).toFixed(2) + ' MH/s';
  } else if (hashrate >= 1e3) {
    return (hashrate / 1e3).toFixed(2) + ' KH/s';
  } else {
    return hashrate.toFixed(2) + ' H/s';
  }
}

 