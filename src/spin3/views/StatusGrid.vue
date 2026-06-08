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

    <main class="grid-container">
      <div class="status-grid">
        <div v-for="mc in 48" :key="mc" 
             class="status-card" 
             :style="getStatusStyle(mc)">
          <div class="mc-id">MC {{ mc }}</div>
          <div class="mc-speed">
            <span class="value">{{ Math.round(getStatus(mc)?.value || 0) }}</span>
            <span class="unit">RPM</span>
          </div>
          <div class="mc-status-text">{{ getStatusText(mc) }}</div>
          <div class="mc-ago">{{ getTimeAgo(getStatus(mc)?.time) }}</div>
        </div>
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
    await telemetry.fetchStatus('machine_telemetry', 'speed')
    lastRefresh.value = new Date().toLocaleTimeString()
  } finally {
    isLoading.value = false
  }
}

const getStatus = (mcId) => {
  return telemetry.machineStatus[mcId] || telemetry.machineStatus[mcId.toString()]
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
</style>
