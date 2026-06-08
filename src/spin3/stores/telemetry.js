import { defineStore } from 'pinia'
import axios from 'axios'

// In development, we use port 8000. In production (Docker), Nginx proxies /spin3 to the backend.
const API_BASE_URL = import.meta.env.DEV 
  ? `http://${window.location.hostname}:8000` 
  : `${window.location.origin}`

export const useTelemetryStore = defineStore('telemetry', {
  state: () => ({
    telemetryData: {},
    machineStatus: {} // Store latest values: { mc_no: { value, time } }
  }),
  actions: {
    async fetchStatus(measurement, field) {
      try {
        const response = await axios.get(`${API_BASE_URL}/spin3/status`, {
          params: { measurement, field }
        })
        this.machineStatus = response.data
      } catch (error) {
        console.error('Error fetching status:', error)
      }
    },
    async fetchTelemetry(measurement, field, mc_no = null, range_h = 1, start = null, end = null) {
      try {
        const params = { measurement, field, mc_no }
        if (start && end) {
          params.start = start
          params.end = end
        } else {
          params.range_h = range_h
        }

        const response = await axios.get(`${API_BASE_URL}/spin3/telemetry`, { params })
        const key = mc_no ? `${measurement}_${field}_${mc_no}` : `${measurement}_${field}`
        this.telemetryData[key] = response.data
        return response.data
      } catch (error) {
        console.error('Error fetching telemetry:', error)
        // Clear data on error to prevent showing stale results
        const key = mc_no ? `${measurement}_${field}_${mc_no}` : `${measurement}_${field}`
        this.telemetryData[key] = []
        throw error
      }
    }
  },
  getters: {
    getData: (state) => (measurement, field, mc_no = null) => {
      const key = mc_no ? `${measurement}_${field}_${mc_no}` : `${measurement}_${field}`
      return state.telemetryData[key] || []
    }
  }
})
