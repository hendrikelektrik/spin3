<template>
  <div class="machine-detail-view">
    <header class="detail-header">
      <div class="left-section">
        <router-link to="/spin3/status" class="back-link">← Back to Grid</router-link>
        <h1>Machine {{ id }}</h1>
        <div class="status-badge" :style="{ backgroundColor: getStatusColor() }">
          {{ getStatusText() }}
        </div>
      </div>
      <div class="right-section">
        <div class="last-update">Last Updated: {{ lastRefresh }}</div>
        <div v-if="isLoading" class="mini-spinner"></div>
      </div>
    </header>

    <div class="dashboard-grid" :class="{ 'loading-dim': isLoading }">
      <!-- Loading Overlay -->
      <div v-if="isLoading" class="loading-overlay">
        <div class="loader"></div>
        <div class="loading-text">Fetching latest data...</div>
      </div>

      <!-- Empty State Overlay -->
      <div v-if="!isLoading && !details.time" class="no-data-notice">
        No recent data found for Machine {{ id }}. 
        <br/><small>Showing default values.</small>
      </div>

      <!-- Live Metrics Cards -->
      <div class="metric-card">
        <div class="label">Speed</div>
        <div class="value">{{ Math.round(details.speed || 0) }} <span class="unit">RPM</span></div>
      </div>
      <div class="metric-card">
        <div class="label">Efficiency</div>
        <div class="value">{{ (details.efficiency || 0).toFixed(1) }} <span class="unit">%</span></div>
      </div>
      <div class="metric-card">
        <div class="label">Avg Speed</div>
        <div class="value">{{ Math.round(details.avg_speed || 0) }} <span class="unit">RPM</span></div>
      </div>
      <div class="metric-card">
        <div class="label">Present Length</div>
        <div class="value">{{ Math.round(details.present_length || 0) }} <span class="unit">m</span></div>
      </div>
      <div class="metric-card">
        <div class="label">Target Length</div>
        <div class="value">{{ Math.round(details.max_length || 0) }} <span class="unit">m</span></div>
      </div>
      <div class="metric-card highlight-metric" v-if="details.minutes_remaining !== null">
        <div class="label">Estimated Time</div>
        <div class="value">{{ details.minutes_remaining }} <span class="unit">mins</span></div>
      </div>
      <div class="metric-card">
        <div class="label">Yarn Count (NE)</div>
        <div class="value">{{ details.ne_y || '-' }}</div>
      </div>
    </div>

    <div v-if="Number(details.step) === 6" class="doffing-alert-bar" :class="isForcedDoff ? 'forced' : 'natural'">
      <div class="alert-content">
        <span class="alert-icon">⚠️</span>
        <span class="alert-text">
          <strong>{{ isForcedDoff ? 'FORCED DOFFING' : 'NATURAL DOFFING' }}</strong> 
          - Machine stopped at {{ Math.round(details.present_length) }}m 
          (Target: {{ Math.round(details.max_length) }}m)
        </span>
      </div>
    </div>

    <div class="main-sections" :class="{ 'loading-dim': isLoading }">
      <!-- Shift Performance Table -->
      <section class="shift-section">
        <h2>Shift Performance</h2>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Shift</th>
                <th>Production Count</th>
                <th>Efficiency (%)</th>
                <th>Stops</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Shift 1</td>
                <td>{{ details.shift_1_count || 0 }}</td>
                <td>{{ (details.shift_1_efficiency || 0).toFixed(1) }}%</td>
                <td>{{ details.shift_1_stop || 0 }}</td>
              </tr>
              <tr>
                <td>Shift 2</td>
                <td>{{ details.shift_2_count || 0 }}</td>
                <td>{{ (details.shift_2_efficiency || 0).toFixed(1) }}%</td>
                <td>{{ details.shift_2_stop || 0 }}</td>
              </tr>
              <tr>
                <td>Shift 3</td>
                <td>{{ details.shift_3_count || 0 }}</td>
                <td>{{ (details.shift_3_efficiency || 0).toFixed(1) }}%</td>
                <td>{{ details.shift_3_stop || 0 }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Speed Trend Chart -->
      <section class="chart-section">
        <h2>Speed Profile (Last 24h)</h2>
        <div class="chart-container">
          <v-chart class="chart" :option="chartOption" autoresize />
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useTelemetryStore } from '../stores/telemetry'
import { STATUS_CONFIG } from '../config'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  TitleComponent,
  LegendComponent
} from 'echarts/components'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  LineChart,
  GridComponent,
  TooltipComponent,
  TitleComponent,
  LegendComponent
])

const props = defineProps({
  id: {
    type: String,
    required: true
  }
})

const telemetry = useTelemetryStore()
const isLoading = ref(false)
const lastRefresh = ref('Never')
let pollInterval = null

const details = computed(() => telemetry.machineDetails)

const isForcedDoff = computed(() => {
  if (Number(details.value.step) !== 6) return false
  const present = details.value.present_length || 0
  const max = details.value.max_length || 0
  // Allow a small 1% margin for "Natural" doffing
  return present < (max * 0.99)
})

const getStatusColor = () => {
  if (!details.value.time) return STATUS_CONFIG.colors.noData
  
  const secondsSinceLastData = (new Date() - new Date(details.value.time)) / 1000
  if (secondsSinceLastData > STATUS_CONFIG.logic.staleDataThreshold) return STATUS_CONFIG.colors.noData

  if (Number(details.value.step) === 6) return STATUS_CONFIG.colors.doffing
  if (details.value.speed > STATUS_CONFIG.logic.speedThreshold) return STATUS_CONFIG.colors.runningGood
  
  const comm = Number(details.value.comm_ok)
  if (comm === 0) return STATUS_CONFIG.colors.commError
  if (comm === 1) return STATUS_CONFIG.colors.stopped
  
  return STATUS_CONFIG.colors.noData
}

const getStatusText = () => {
  if (!details.value.time) return STATUS_CONFIG.logic.labels.noData
  
  const secondsSinceLastData = (new Date() - new Date(details.value.time)) / 1000
  if (secondsSinceLastData > STATUS_CONFIG.logic.staleDataThreshold) return STATUS_CONFIG.logic.labels.noData

  if (Number(details.value.step) === 6) return STATUS_CONFIG.logic.labels.doffing
  if (details.value.speed > STATUS_CONFIG.logic.speedThreshold) return STATUS_CONFIG.logic.labels.runningGood
  
  const comm = Number(details.value.comm_ok)
  if (comm === 0) return STATUS_CONFIG.logic.labels.commError
  if (comm === 1) return STATUS_CONFIG.logic.labels.stopped
  
  return STATUS_CONFIG.logic.labels.noData
}

const chartData = computed(() => {
  const raw = telemetry.getData('machine_telemetry', 'speed', props.id)
  return raw.map(p => [new Date(p.time).getTime(), p.speed])
})

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params) => {
      const p = params[0]
      const date = new Date(p.value[0]).toLocaleTimeString()
      return `${date}<br/>Speed: <b>${Math.round(p.value[1])} RPM</b>`
    }
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true
  },
  xAxis: {
    type: 'time',
    boundaryGap: false,
    axisLabel: {
      color: '#7f8c8d'
    }
  },
  yAxis: {
    type: 'value',
    name: 'RPM',
    splitLine: {
      lineStyle: {
        type: 'dashed',
        color: '#eee'
      }
    }
  },
  series: [
    {
      name: 'Speed',
      type: 'line',
      smooth: true,
      showSymbol: false,
      data: chartData.value,
      lineStyle: {
        width: 3,
        color: '#42b983'
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(66, 185, 131, 0.3)' },
            { offset: 1, color: 'rgba(66, 185, 131, 0)' }
          ]
        }
      }
    }
  ]
}))

let updateRequestId = 0

const updateData = async () => {
  const requestId = ++updateRequestId
  isLoading.value = true
  
  // Clear previous metrics immediately to prevent flickering old data
  telemetry.clearMachineDetails()
  
  try {
    // Fetch basic details first (fast)
    await telemetry.fetchMachineDetail('machine_telemetry', props.id)
    
    // Check if this is still the active request
    if (requestId !== updateRequestId) return

    // Fetch historical data for the chart (potentially slower)
    await telemetry.fetchTelemetry('machine_telemetry', 'speed', props.id, 24)
    
    if (requestId === updateRequestId) {
      lastRefresh.value = new Date().toLocaleTimeString()
    }
  } catch (error) {
    console.error('Update failed:', error)
  } finally {
    if (requestId === updateRequestId) {
      isLoading.value = false
    }
  }
}

onMounted(() => {
  updateData()
  pollInterval = setInterval(updateData, 10000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})

watch(() => props.id, () => {
  updateData()
})
</script>

<style scoped>
.machine-detail-view {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.05);
}

.left-section {
  display: flex;
  align-items: center;
  gap: 20px;
}

.back-link {
  text-decoration: none;
  color: #7f8c8d;
  font-weight: 500;
}

.back-link:hover {
  color: #2c3e50;
}

.detail-header h1 {
  margin: 0;
  font-size: 1.8rem;
  color: #2c3e50;
}

.status-badge {
  color: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.right-section {
  text-align: right;
  display: flex;
  align-items: center;
  gap: 15px;
}

.last-update {
  font-size: 0.85rem;
  color: #95a5a6;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.metric-card {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  text-align: center;
}

.metric-card .label {
  font-size: 0.85rem;
  color: #7f8c8d;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.metric-card .value {
  font-size: 1.8rem;
  font-weight: bold;
  color: #2c3e50;
}

.metric-card .unit {
  font-size: 0.9rem;
  color: #95a5a6;
  margin-left: 4px;
}

.metric-card.highlight-metric {
  background: #42b983;
}

.metric-card.highlight-metric .label,
.metric-card.highlight-metric .value,
.metric-card.highlight-metric .unit {
  color: white;
}

.main-sections {
  display: grid;
  grid-template-columns: 1fr;
  gap: 30px;
}

@media (min-width: 1024px) {
  .main-sections {
    grid-template-columns: 1fr 1.5fr;
  }
}

section {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.05);
}

section h2 {
  margin-top: 0;
  margin-bottom: 20px;
  font-size: 1.2rem;
  color: #2c3e50;
  border-bottom: 2px solid #f8f9fa;
  padding-bottom: 10px;
}

.table-container {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th {
  text-align: left;
  color: #7f8c8d;
  font-size: 0.85rem;
  padding: 12px;
  border-bottom: 1px solid #eee;
}

td {
  padding: 12px;
  border-bottom: 1px solid #f8f9fa;
  color: #2c3e50;
  font-weight: 500;
}

.chart-container {
  height: 400px;
  width: 100%;
}

.chart {
  height: 100%;
  width: 100%;
}

.mini-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #f3f3f3;
  border-top: 2px solid #42b983;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* Doffing Alert Styles */
.doffing-alert-bar {
  padding: 15px 20px;
  border-radius: 12px;
  margin-bottom: 30px;
  display: flex;
  align-items: center;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.doffing-alert-bar.natural {
  background-color: #f39c12; /* Natural Doff Orange */
  color: white;
}

.doffing-alert-bar.forced {
  background-color: #3498db; /* Forced Doff Blue (to distinguish from error) */
  color: white;
}

.alert-content {
  display: flex;
  align-items: center;
  gap: 15px;
}

.alert-icon {
  font-size: 1.5rem;
}

.alert-text {
  font-size: 1rem;
}

.alert-text strong {
  font-size: 1.1rem;
  margin-right: 5px;
}

.loading-dim {
  opacity: 0.4;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.6);
  z-index: 10;
  border-radius: 12px;
}

.loader {
  width: 40px;
  height: 40px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #42b983;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 10px;
}

.loading-text {
  color: #2c3e50;
  font-weight: 500;
  font-size: 0.9rem;
}

.no-data-notice {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(255, 255, 255, 0.9);
  padding: 20px 40px;
  border-radius: 8px;
  border: 1px solid #eee;
  text-align: center;
  z-index: 100;
  color: #7f8c8d;
  font-weight: bold;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.no-data-notice small {
  font-weight: normal;
  display: block;
  margin-top: 5px;
}
</style>
