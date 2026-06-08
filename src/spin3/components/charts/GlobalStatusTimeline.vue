<template>
  <div class="chart-container">
    <div v-if="!data || data.length === 0" class="no-data-overlay">
      No data available for this period
    </div>
    <v-chart 
      class="chart" 
      :option="option" 
      :update-options="{ notMerge: true }"
      autoresize 
    />
  </div>
</template>

<script setup>
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { CustomChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  TitleComponent,
  DataZoomComponent,
  VisualMapComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { computed } from 'vue'
import { STATUS_CONFIG } from '../../config'

use([
  CanvasRenderer,
  CustomChart,
  GridComponent,
  TooltipComponent,
  TitleComponent,
  DataZoomComponent,
  VisualMapComponent
])

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  },
  title: {
    type: String,
    default: ''
  },
  height: {
    type: [String, Number],
    default: 800
  },
  startTime: {
    type: [Date, Number, String],
    default: null
  },
  endTime: {
    type: [Date, Number, String],
    default: null
  }
})

const getStatusColor = (speed, comm_ok, step) => {
  if (Number(step) === 6) {
    return STATUS_CONFIG.colors.doffing
  }
  if (speed > STATUS_CONFIG.logic.speedThreshold) {
    return STATUS_CONFIG.colors.runningGood
  }
  const comm = Number(comm_ok)
  if (comm === 0) return STATUS_CONFIG.colors.commError
  if (comm === 1) return STATUS_CONFIG.colors.stopped
  return STATUS_CONFIG.colors.noData
}

const getStatusLabel = (speed, comm_ok, step) => {
  if (Number(step) === 6) {
    return STATUS_CONFIG.logic.labels.doffing
  }
  if (speed > STATUS_CONFIG.logic.speedThreshold) {
    return STATUS_CONFIG.logic.labels.runningGood
  }
  const comm = Number(comm_ok)
  if (comm === 0) return STATUS_CONFIG.logic.labels.commError
  if (comm === 1) return STATUS_CONFIG.logic.labels.stopped
  return STATUS_CONFIG.logic.labels.noData
}

const option = computed(() => {
  const categories = []
  for (let i = 1; i <= 48; i++) {
    categories.push(`MC ${i}`)
  }

  // Group data by mc_no
  const machineGroups = {}
  console.log('Timeline receiving data sample:', props.data.slice(0, 3)) // Debug log
  props.data.forEach(point => {
    if (!machineGroups[point.mc_no]) machineGroups[point.mc_no] = []
    machineGroups[point.mc_no].push(point)
  })

  const chartData = []
  
  Object.keys(machineGroups).forEach(mc_no => {
    const points = machineGroups[mc_no].sort((a, b) => new Date(a.time) - new Date(b.time))
    const mcIdx = parseInt(mc_no) - 1
    if (mcIdx < 0 || mcIdx >= 48) return

    let currentBlock = null

    for (let i = 0; i < points.length; i++) {
      const time = new Date(points[i].time).getTime()
      const speed = points[i].speed || 0
      const comm_ok = points[i].comm_ok || 0
      const step = points[i].step || 0
      const statusLabel = getStatusLabel(speed, comm_ok, step)
      const statusColor = getStatusColor(speed, comm_ok, step)

      if (!currentBlock) {
        currentBlock = {
          start: time,
          lastPointTime: time,
          label: statusLabel,
          color: statusColor,
          speed: speed,
          comm_ok: comm_ok,
          step: step
        }
        continue
      }

      const gap = time - currentBlock.lastPointTime
      
      // If status changed OR there's a large gap (10m), end current block and start new one
      // Gaps larger than 10m are implicitly "OFF" (no data)
      if (statusLabel !== currentBlock.label || gap > 600000) {
        chartData.push({
          name: currentBlock.label,
          value: [
            mcIdx,
            currentBlock.start,
            currentBlock.lastPointTime,
            currentBlock.speed,
            currentBlock.comm_ok,
            currentBlock.step
          ],
          itemStyle: {
            normal: {
              color: currentBlock.color
            }
          }
        })

        currentBlock = {
          start: time,
          lastPointTime: time,
          label: statusLabel,
          color: statusColor,
          speed: speed,
          comm_ok: comm_ok,
          step: step
        }
      } else {
        // Same status and small gap, just extend the block
        currentBlock.lastPointTime = time
      }
    }

    // Push the last block
    if (currentBlock) {
      chartData.push({
        name: currentBlock.label,
        value: [
          mcIdx,
          currentBlock.start,
          currentBlock.lastPointTime,
          currentBlock.speed,
          currentBlock.comm_ok,
          currentBlock.step
        ],
        itemStyle: {
          normal: {
            color: currentBlock.color
          }
        }
      })
    }
  })

  return {
    animation: false,
    title: {
      show: !!props.title,
      text: props.title,
      left: 'center'
    },
    tooltip: {
      confine: true,
      enterable: false,
      transitionDuration: 0,
      formatter: (params) => {
        const mcName = categories[params.value[0]]
        const startTime = new Date(params.value[1])
        const endTime = new Date(params.value[2])
        const status = params.name
        const speed = Math.round(params.value[3])
        const step = params.value[5]
        
        const durationMs = endTime - startTime
        const mins = Math.floor(durationMs / 60000)
        const secs = Math.floor((durationMs % 60000) / 1000)
        const durationStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`

        return `<b>${mcName} - ${status}</b><br/>` +
               `Duration: ${durationStr}<br/>` +
               `Speed: ${speed} RPM | Step: ${step}<br/>` +
               `Range: ${startTime.toLocaleTimeString()} - ${endTime.toLocaleTimeString()}`
      }
    },
    grid: {
      top: props.title ? 40 : 10,
      bottom: 20, // Reduced since slider is removed
      left: 80,
      right: 40,
      containLabel: true
    },
    xAxis: {
      type: 'time',
      boundaryGap: false,
      splitLine: { show: true, lineStyle: { type: 'dashed' } },
      min: props.startTime ? new Date(props.startTime).getTime() : undefined,
      max: props.endTime ? new Date(props.endTime).getTime() : undefined,
      axisLabel: {
        hideOverlap: true
      }
    },
    yAxis: {
      type: 'category',
      data: categories,
      splitLine: { show: true },
      inverse: true,
      axisLabel: { 
        fontSize: 11,
        margin: 12
      },
      axisLine: {
        show: true,
        lineStyle: { color: '#ddd' }
      }
    },
    series: [
      {
        type: 'custom',
        renderItem: (params, api) => {
          const categoryIndex = api.value(0)
          const start = api.coord([api.value(1), categoryIndex])
          const end = api.coord([api.value(2), categoryIndex])
          const height = api.size([0, 1])[1] * 0.8

          return {
            type: 'rect',
            shape: {
              x: start[0],
              y: start[1] - height / 2,
              width: Math.max(end[0] - start[0], 0.5),
              height: height
            },
            style: api.style()
          }
        },
        itemStyle: {
          opacity: 0.8
        },
        encode: {
          x: [1, 2],
          y: 0
        },
        data: chartData,
        progressive: 0, // Disable progressive rendering for instant display
        animation: false
      }
    ]
  }
})
</script>

<style scoped>
.chart-container {
  height: v-bind(height + 'px');
  width: 100%;
  background: transparent;
  padding: 0;
}
.chart {
  height: 100%;
  width: 100%;
}

.no-data-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(255, 255, 255, 0.9);
  padding: 20px 40px;
  border-radius: 8px;
  border: 1px solid #ddd;
  color: #7f8c8d;
  font-weight: bold;
  z-index: 10;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
</style>
