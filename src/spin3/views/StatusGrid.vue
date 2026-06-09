<template>
  <div class="status-grid-view">
    <header class="view-header">
      <div class="title-section">
        <h1>Spin3 Real-Time Status</h1>
        <div class="refresh-timer">Updated: {{ lastRefresh }}</div>
      </div>
      <div class="header-right">
        <div v-if="isLoading" class="fetch-indicator">
          <span class="mini-spinner"></span>
        </div>
        <div class="legend">
          <div v-for="(color, key) in STATUS_CONFIG.colors" :key="key" class="legend-item">
            <span class="dot" :style="{ backgroundColor: color }"></span>
            {{ STATUS_CONFIG.logic.labels[key] }}
          </div>
        </div>
      </div>
    </header>

    <div class="summary-ribbon">
      <div class="summary-card">
        <div class="summary-icon">📦</div>
        <div class="summary-info">
          <div class="summary-label">Total Production</div>
          <div class="summary-value">{{ (telemetry.factorySummary.total_production || 0).toLocaleString() }}</div>
        </div>
      </div>
      <div class="summary-card">
        <div class="summary-icon">📈</div>
        <div class="summary-info">
          <div class="summary-label">Avg Efficiency</div>
          <div class="summary-value">{{ (telemetry.factorySummary.avg_efficiency || 0).toFixed(1) }}%</div>
        </div>
      </div>
      <div class="summary-card">
        <div class="summary-icon">⚙️</div>
        <div class="summary-info">
          <div class="summary-label">Active Machines</div>
          <div class="summary-value">{{ telemetry.factorySummary.running_count || 0 }} / {{ telemetry.factorySummary.total_machines || 0 }}</div>
        </div>
      </div>
      <div class="summary-card" :class="{ 'highlight': (telemetry.factorySummary.doffing_count || 0) > 0 }">
        <div class="summary-icon">🚜</div>
        <div class="summary-info">
          <div class="summary-label">Doffing Now</div>
          <div class="summary-value">
            <template v-if="telemetry.factorySummary.doffing_count > 0">
              <span v-for="(mc, idx) in telemetry.factorySummary.doffing_machines" :key="mc">
                MC {{ mc }}{{ idx < telemetry.factorySummary.doffing_machines.length - 1 ? ', ' : '' }}
              </span>
            </template>
            <template v-else>0</template>
          </div>
        </div>
      </div>
      <div class="summary-card" :class="{ 'soon-highlight': (telemetry.factorySummary.doffing_soon_count || 0) > 0 }">
        <div class="summary-icon">⏰</div>
        <div class="summary-info">
          <div class="summary-label">Doffing Soon</div>
          <div class="summary-value">
            <template v-if="telemetry.factorySummary.doffing_soon_count > 0">
              <span v-for="(mc, idx) in telemetry.factorySummary.doffing_soon_machines" :key="mc">
                MC {{ mc }}{{ idx < telemetry.factorySummary.doffing_soon_machines.length - 1 ? ', ' : '' }}
              </span>
            </template>
            <template v-else>0</template>
          </div>
        </div>
      </div>
    </div>

    <main class="grid-container">
      <div class="status-grid">
        <router-link v-for="mc in 48" :key="mc" 
             :to="`/spin3/machine/${mc}`"
             class="status-card" 
             :class="{ 'doffing-soon-card': isDoffingSoon(mc) }"
             :style="getStatusStyle(mc)">
          <div class="mc-id">MC {{ mc }}</div>
          
          <div class="mc-top-right" v-if="getStatus(mc)?.minutes_remaining">
             <span class="doff-time">{{ getStatus(mc)?.minutes_remaining }}m</span>
          </div>

          <div v-if="isRunning(mc)" class="mc-speed">
            <span class="value">{{ Math.round(getStatus(mc)?.value || 0) }}</span>
            <span class="unit">RPM</span>
          </div>
          <div v-else class="mc-speed-placeholder"></div>
          <div class="mc-status-text">{{ getStatusText(mc) }}</div>
          <div class="mc-progress-container" v-if="getStatus(mc)?.max_length > 0">
            <div class="mc-progress-bar" 
                 :style="{ width: Math.min(100, ((getStatus(mc)?.present_length || 0) / (getStatus(mc)?.max_length || 1)) * 100) + '%' }">
            </div>
          </div>
          <div class="mc-ago">{{ getTimeAgo(getStatus(mc)?.time) }}</div>
        </router-link>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useTelemetryStore } from '../stores/telemetry'
import { STATUS_CONFIG } from '../config'

const telemetry = useTelemetryStore()
const lastRefresh = ref('Never')
const isLoading = ref(true)
let pollInterval = null

const updateStatus = async () => {
  isLoading.value = true
  try {
    await Promise.all([
      telemetry.fetchStatus('machine_telemetry', 'speed'),
      telemetry.fetchFactorySummary('machine_telemetry')
    ])
    lastRefresh.value = new Date().toLocaleTimeString()
  } finally {
    isLoading.value = false
  }
}

const getStatus = (mcId) => {
  return telemetry.machineStatus[mcId] || telemetry.machineStatus[mcId.toString()]
}

const isDoffingSoon = (mcId) => {
  const status = getStatus(mcId)
  return status && 
         status.minutes_remaining !== null && 
         status.minutes_remaining > 0 && 
         status.minutes_remaining <= STATUS_CONFIG.logic.doffingSoonThreshold
}

const isStale = (timestamp) => {
  if (!timestamp) return true
  const secondsSinceLastData = (new Date() - new Date(timestamp)) / 1000
  return secondsSinceLastData > STATUS_CONFIG.logic.staleDataThreshold
}

const getStatusStyle = (mcId) => {
  const status = getStatus(mcId)
  let colorKey = 'noData'
  
  if (status && !isStale(status.time)) {
    if (Number(status.step) === 6) {
      colorKey = 'doffing'
    } else if (status.value > STATUS_CONFIG.logic.speedThreshold) {
      colorKey = 'runningGood'
    } else {
      const comm = Number(status.comm_ok)
      if (comm === 0) colorKey = 'commError'
      else if (comm === 1) colorKey = 'stopped'
    }
  }
  
  return { backgroundColor: STATUS_CONFIG.colors[colorKey] }
}

const getStatusText = (mcId) => {
  const status = getStatus(mcId)
  if (!status || isStale(status.time)) return STATUS_CONFIG.logic.labels.noData
  
  if (Number(status.step) === 6) {
    return STATUS_CONFIG.logic.labels.doffing
  }
  
  if (status.value > STATUS_CONFIG.logic.speedThreshold) {
    return STATUS_CONFIG.logic.labels.runningGood
  }
  
  const comm = Number(status.comm_ok)
  if (comm === 0) return STATUS_CONFIG.logic.labels.commError
  if (comm === 1) return STATUS_CONFIG.logic.labels.stopped
  
  return STATUS_CONFIG.logic.labels.noData
}

const getTimeAgo = (timestamp) => {
  if (!timestamp) return '-'
  const diff = Math.floor((new Date() - new Date(timestamp)) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

const isRunning = (mcId) => {
  const status = getStatus(mcId)
  if (!status || isStale(status.time)) return false
  return (
    Number(status.step) !== 6 && 
    Number(status.comm_ok) === 1 && 
    status.value > STATUS_CONFIG.logic.speedThreshold
  )
}

onMounted(() => {
  updateStatus()
  pollInterval = setInterval(updateStatus, 5000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})
</script>

<style scoped>
.status-grid-view {
  padding: 20px;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 20px;
  background: white;
  padding: 15px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.title-section h1 {
  margin: 0;
  font-size: 1.4rem;
  color: #2c3e50;
}

.refresh-timer {
  font-size: 0.75rem;
  color: #7f8c8d;
}

.legend {
  display: flex;
  gap: 15px;
  font-size: 0.75rem;
  font-weight: bold;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 2px;
  background: #eee;
  border: 1px solid #eee;
}

.status-card {
  color: white;
  padding: 15px 5px;
  text-align: center;
  transition: all 0.3s ease;
  text-decoration: none;
  display: block;
  position: relative;
}

.status-card.doffing-soon-card {
  box-shadow: inset 0 0 0 3px #f1c40f;
  animation: pulse-soon 2s infinite;
}

@keyframes pulse-soon {
  0% { filter: brightness(1); }
  50% { filter: brightness(1.2); }
  100% { filter: brightness(1); }
}

.mc-top-right {
  position: absolute;
  top: 2px;
  right: 5px;
}

.doff-time {
  font-size: 0.65rem;
  font-weight: bold;
  background: rgba(0,0,0,0.3);
  padding: 1px 4px;
  border-radius: 4px;
}

.status-card:hover {
  filter: brightness(1.2);
}

.mc-id {
  font-weight: bold;
  font-size: 0.9rem;
  opacity: 0.9;
}

.mc-speed .value {
  font-size: 1.8rem;
  font-weight: bold;
}

.mc-speed .unit {
  font-size: 0.7rem;
  margin-left: 2px;
}

.mc-speed-placeholder {
  height: 2.5rem; /* Matches the height of mc-speed */
}

.mc-status-text {
  font-size: 0.8rem;
  font-weight: bold;
  margin-top: 5px;
  letter-spacing: 0.5px;
}

.mc-ago {
  font-size: 0.7rem;
  opacity: 0.6;
  margin-top: 5px;
}

.mc-progress-container {
  width: 80%;
  height: 4px;
  background: rgba(255, 255, 255, 0.2);
  margin: 8px auto 0;
  border-radius: 2px;
  overflow: hidden;
}

.mc-progress-bar {
  height: 100%;
  background: rgba(255, 255, 255, 0.8);
  transition: width 0.5s ease;
}

/* Loading Indicators */
.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.fetch-indicator {
  display: flex;
  align-items: center;
}

.mini-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid #e0e0e0;
  border-top: 2px solid #42b983;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* Summary Ribbon Styles */
.summary-ribbon {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  margin-bottom: 20px;
}

.summary-card {
  background: white;
  padding: 15px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 15px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
  border-left: 4px solid #42b983;
}

.summary-card.highlight {
  border-left-color: #f39c12; /* Doffing Orange */
  background: #fff9f0;
}

.summary-card.soon-highlight {
  border-left-color: #f1c40f; /* Yellow */
  background: #fffeeb;
}

.summary-icon {
  font-size: 1.5rem;
  background: #f8f9fa;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.summary-info {
  display: flex;
  flex-direction: column;
}

.summary-label {
  font-size: 0.75rem;
  color: #7f8c8d;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.summary-value {
  font-size: 1.2rem;
  font-weight: bold;
  color: #2c3e50;
}
</style>
