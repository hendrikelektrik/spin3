<template>
  <div class="history-timeline-view">
    <header class="view-header">
      <div class="title-section">
        <h1>Status Timeline</h1>
        <div v-if="isLoading" class="loader">
          <div class="spinner"></div>
        </div>
      </div>
      <div class="controls">
        <div class="control-group">
          <label>View Mode:</label>
          <select v-model="viewMode" @change="onModeChange">
            <option value="relative">Recent</option>
            <option value="absolute">History</option>
          </select>
        </div>

        <div v-if="viewMode === 'relative'" class="control-group">
          <label>Range:</label>
          <select v-model="timeRange" @change="fetchGlobalHistory()">
            <option :value="1">Last 1 Hour</option>
            <option :value="3">Last 3 Hours</option>
            <option :value="6">Last 6 Hours</option>
            <option :value="12">Last 12 Hours</option>
            <option :value="24">Last 24 Hours</option>
          </select>
        </div>

        <div v-else class="control-group">
          <label>Select Date:</label>
          <input type="date" v-model="selectedDate" @change="fetchGlobalHistory()">
        </div>

        <div class="control-group">
          <label>Auto Refresh:</label>
          <select v-model="refreshRate" @change="setupPolling" :disabled="viewMode === 'absolute'">
            <option :value="0">Off</option>
            <option :value="10000">10s</option>
            <option :value="30000">30s</option>
            <option :value="60000">1m</option>
            <option :value="300000">5m</option>
          </select>
        </div>
      </div>
    </header>

    <main>
      <div class="chart-section">
        <div v-if="viewMode === 'absolute'" class="history-label">
          Showing history for: <strong>{{ selectedDate }}</strong> (00:00 - 23:59)
        </div>
        <GlobalStatusTimeline 
          :data="telemetry.getData('machine_telemetry', 'speed,comm_ok,step')"
          title=""
          height="900"
          :startTime="chartStartTime"
          :endTime="chartEndTime"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useTelemetryStore } from '../stores/telemetry'
import GlobalStatusTimeline from '../components/charts/GlobalStatusTimeline.vue'

const telemetry = useTelemetryStore()
const viewMode = ref('relative')
const selectedDate = ref(new Date().toISOString().split('T')[0])
const timeRange = ref(1) // Hours
const refreshRate = ref(60000) // Default to 1m for history
const isLoading = ref(false)
let pollInterval = null

// Compute chart boundaries for fixed scaling
const chartStartTime = computed(() => {
  if (viewMode.value === 'absolute') {
    return new Date(`${selectedDate.value}T00:00:00Z`).getTime()
  }
  return new Date().getTime() - (timeRange.value * 60 * 60 * 1000)
})

const chartEndTime = computed(() => {
  if (viewMode.value === 'absolute') {
    return new Date(`${selectedDate.value}T23:59:59Z`).getTime()
  }
  return new Date().getTime()
})

const fetchGlobalHistory = async () => {
  isLoading.value = true
  try {
    let start = null
    let end = null
    
    if (viewMode.value === 'absolute') {
      // Fetch the full day from midnight to midnight (UTC for now, align with DB)
      start = `${selectedDate.value}T00:00:00Z`
      end = `${selectedDate.value}T23:59:59Z`
    }
    
    await telemetry.fetchTelemetry('machine_telemetry', 'speed,comm_ok,step', null, timeRange.value, start, end)
  } catch (error) {
    console.error('Failed to fetch history:', error)
  } finally {
    isLoading.value = false
  }
}

const onModeChange = () => {
  if (viewMode.value === 'absolute') {
    if (pollInterval) clearInterval(pollInterval)
  } else {
    setupPolling()
  }
  fetchGlobalHistory()
}

const setupPolling = () => {
  if (pollInterval) clearInterval(pollInterval)
  if (refreshRate.value > 0 && viewMode.value === 'relative') {
    pollInterval = setInterval(fetchGlobalHistory, refreshRate.value)
  }
}

onMounted(() => {
  fetchGlobalHistory()
  setupPolling()
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})
</script>

<style scoped>
.history-timeline-view {
  padding: 10px;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  background: white;
  padding: 10px 15px;
  border-radius: 6px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.title-section {
  display: flex;
  align-items: center;
  gap: 20px;
}

.title-section h1 {
  margin: 0;
  font-size: 1.4rem;
  color: #2c3e50;
}

.loader {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #42b983;
  font-size: 0.85rem;
  font-weight: bold;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #e0e0e0;
  border-top: 2px solid #42b983;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.controls {
  display: flex;
  gap: 20px;
}

.control-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.control-group label {
  font-size: 0.8rem;
  font-weight: bold;
  color: #7f8c8d;
  text-transform: uppercase;
}

.control-group select {
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid #ddd;
  background: #f8f9fa;
  font-size: 0.85rem;
  color: #2c3e50;
  cursor: pointer;
}

.control-group select:focus {
  outline: none;
  border-color: #42b983;
}

.chart-section {
  background: white;
  padding: 0;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
  overflow: hidden;
}

.history-label {
  padding: 10px 20px;
  background: #f1f3f5;
  border-bottom: 1px solid #e9ecef;
  font-size: 0.85rem;
  color: #495057;
}

.history-label strong {
  color: #2c3e50;
}
</style>
