// Analytics Dashboard JavaScript

// State management
let currentResults = [];
let currentOffset = 0;
const LIMIT = 100;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
  initializeEventListeners();
  loadPoolStats();
  loadTopWorkers();
  setDefaultTimeRange();
});

function initializeEventListeners() {
  // Time range change
  document.getElementById('timeRange').addEventListener('change', handleTimeRangeChange);
  
  // Query button
  document.getElementById('queryShares').addEventListener('click', queryShares);
  
  // Reset button
  document.getElementById('resetForm').addEventListener('click', resetForm);
  
  // Export buttons
  document.getElementById('exportCsv').addEventListener('click', () => exportResults('csv'));
  document.getElementById('exportJson').addEventListener('click', () => exportResults('json'));
  
  // Load more button
  document.getElementById('loadMoreBtn').addEventListener('click', loadMore);
}

function setDefaultTimeRange() {
  const now = new Date();
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  
  document.getElementById('endTime').value = now.toISOString().slice(0, 16);
  document.getElementById('startTime').value = yesterday.toISOString().slice(0, 16);
}

function handleTimeRangeChange(e) {
  const customTimeRange = document.getElementById('customTimeRange');
  if (e.target.value === 'custom') {
    customTimeRange.style.display = 'flex';
  } else {
    customTimeRange.style.display = 'none';
  }
}

async function loadPoolStats() {
  try {
    const response = await fetch('/analytics/pool-stats');
    const data = await response.json();
    
    document.getElementById('poolHashrate').textContent = formatHashrate(data.hashrate_24h);
    document.getElementById('activeWorkers').textContent = data.active_workers;
    document.getElementById('totalShares').textContent = formatNumber(data.total_shares);
    document.getElementById('bestShare').textContent = formatDifficulty(data.best_share);
  } catch (error) {
    console.error('Error loading pool stats:', error);
  }
}

async function loadTopWorkers() {
  try {
    const response = await fetch('/analytics/top-workers');
    const data = await response.json();
    
    const tbody = document.getElementById('workersBody');
    tbody.innerHTML = '';
    
    data.forEach(worker => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${worker.worker}</td>
        <td>${formatHashrate(worker.hashrate)}</td>
        <td>${formatNumber(worker.total_shares)}</td>
        <td>${(worker.accept_rate * 100).toFixed(1)}%</td>
        <td>${formatDifficulty(worker.best_share)}</td>
        <td>${worker.avg_luck.toFixed(2)}x</td>
      `;
      tbody.appendChild(row);
    });
  } catch (error) {
    console.error('Error loading top workers:', error);
    document.getElementById('workersBody').innerHTML = '<tr><td colspan="6" class="error">Failed to load</td></tr>';
  }
}

async function queryShares() {
  const params = buildQueryParams();
  currentOffset = 0;
  currentResults = [];
  
  try {
    const response = await fetch('/analytics/shares?' + new URLSearchParams(params));
    const data = await response.json();
    
    currentResults = data.shares;
    displayResults(data);
    
    document.getElementById('resultsSection').style.display = 'block';
    
    // Show/hide load more button
    if (data.shares.length >= LIMIT) {
      document.getElementById('loadMore').style.display = 'block';
    } else {
      document.getElementById('loadMore').style.display = 'none';
    }
  } catch (error) {
    alert('Error querying shares: ' + error.message);
  }
}

async function loadMore() {
  currentOffset += LIMIT;
  const params = buildQueryParams();
  params.offset = currentOffset;
  
  try {
    const response = await fetch('/analytics/shares?' + new URLSearchParams(params));
    const data = await response.json();
    
    currentResults = currentResults.concat(data.shares);
    appendResults(data.shares);
    
    if (data.shares.length < LIMIT) {
      document.getElementById('loadMore').style.display = 'none';
    }
  } catch (error) {
    alert('Error loading more results: ' + error.message);
  }
}

function buildQueryParams() {
  const params = {
    limit: LIMIT
  };
  
  // Worker filter
  const worker = document.getElementById('workerFilter').value.trim();
  if (worker) {
    params.worker = worker;
  }
  
  // Time range
  const timeRange = document.getElementById('timeRange').value;
  if (timeRange === 'custom') {
    params.start_time = document.getElementById('startTime').value;
    params.end_time = document.getElementById('endTime').value;
  } else {
    params.time_range = timeRange;
  }
  
  // Difficulty filter
  const minDiff = document.getElementById('minDifficulty').value;
  if (minDiff) {
    params.min_difficulty = minDiff;
  }
  
  // Status filter
  const status = document.getElementById('shareStatus').value;
  if (status !== 'all') {
    params.accepted = status === 'accepted' ? '1' : '0';
  }
  
  return params;
}

function displayResults(data) {
  // Update summary
  const summary = document.getElementById('resultsSummary');
  summary.innerHTML = `
    <div class="summary-item">
      <span class="summary-label">Total Results:</span>
      <span class="summary-value">${data.total_count}</span>
    </div>
    <div class="summary-item">
      <span class="summary-label">Showing:</span>
      <span class="summary-value">${data.shares.length}</span>
    </div>
    <div class="summary-item">
      <span class="summary-label">Average Difficulty:</span>
      <span class="summary-value">${formatDifficulty(data.avg_difficulty)}</span>
    </div>
    <div class="summary-item">
      <span class="summary-label">Total Share Value:</span>
      <span class="summary-value">${formatDifficulty(data.total_share_value)}</span>
    </div>
  `;
  
  // Clear and populate table
  const tbody = document.getElementById('resultsBody');
  tbody.innerHTML = '';
  appendResults(data.shares);
}

function appendResults(shares) {
  const tbody = document.getElementById('resultsBody');
  
  shares.forEach(share => {
    const row = document.createElement('tr');
    const luck = share.actual_difficulty / share.pool_difficulty;
    const statusClass = share.accepted ? 'accepted' : 'rejected';
    
    row.innerHTML = `
      <td>${formatTimestamp(share.ts)}</td>
      <td>${share.worker}</td>
      <td>${formatDifficulty(share.pool_difficulty)}</td>
      <td>${formatDifficulty(share.actual_difficulty)}</td>
      <td class="luck-${luck >= 10 ? 'high' : luck >= 1 ? 'normal' : 'low'}">${luck.toFixed(2)}x</td>
      <td class="status-${statusClass}">${share.accepted ? 'Accepted' : 'Rejected'}</td>
      <td class="mono">${share.job_id.substring(0, 8)}...</td>
    `;
    tbody.appendChild(row);
  });
}

function resetForm() {
  document.getElementById('workerFilter').value = '';
  document.getElementById('timeRange').value = '24h';
  document.getElementById('minDifficulty').value = '';
  document.getElementById('shareStatus').value = 'all';
  document.getElementById('customTimeRange').style.display = 'none';
  document.getElementById('resultsSection').style.display = 'none';
  setDefaultTimeRange();
}

function exportResults(format) {
  if (!currentResults.length) {
    alert('No results to export');
    return;
  }
  
  let content, mimeType, filename;
  
  if (format === 'csv') {
    content = convertToCSV(currentResults);
    mimeType = 'text/csv';
    filename = `shares_${new Date().toISOString()}.csv`;
  } else {
    content = JSON.stringify(currentResults, null, 2);
    mimeType = 'application/json';
    filename = `shares_${new Date().toISOString()}.json`;
  }
  
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function convertToCSV(data) {
  if (!data.length) return '';
  
  const headers = Object.keys(data[0]);
  const csvHeaders = headers.join(',');
  
  const csvRows = data.map(row => {
    return headers.map(header => {
      const value = row[header];
      // Escape quotes and wrap in quotes if contains comma
      if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
        return `"${value.replace(/"/g, '""')}"`;
      }
      return value;
    }).join(',');
  });
  
  return [csvHeaders, ...csvRows].join('\n');
}

// Formatting utilities
function formatTimestamp(ts) {
  const date = new Date(ts);
  return date.toLocaleString();
}

function formatHashrate(hashrate) {
  if (hashrate >= 1e12) {
    return (hashrate / 1e12).toFixed(2) + ' TH/s';
  } else if (hashrate >= 1e9) {
    return (hashrate / 1e9).toFixed(2) + ' GH/s';
  } else if (hashrate >= 1e6) {
    return (hashrate / 1e6).toFixed(2) + ' MH/s';
  } else {
    return (hashrate / 1e3).toFixed(2) + ' KH/s';
  }
}

function formatDifficulty(diff) {
  if (!diff) return '0';
  
  if (diff >= 1e12) {
    return (diff / 1e12).toFixed(2) + 'T';
  } else if (diff >= 1e9) {
    return (diff / 1e9).toFixed(2) + 'G';
  } else if (diff >= 1e6) {
    return (diff / 1e6).toFixed(2) + 'M';
  } else if (diff >= 1e3) {
    return (diff / 1e3).toFixed(2) + 'K';
  } else {
    return diff.toFixed(2);
  }
}

function formatNumber(num) {
  return new Intl.NumberFormat().format(num);
}