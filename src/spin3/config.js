export const STATUS_CONFIG = {
  // Colors (Hex)
  colors: {
    commError: '#9b59b6',    // Purple
    stopped: '#e74c3c',      // Red
    doffing: '#f39c12',      // Orange
    runningGood: '#27ae60',  // Green
    noData: '#7f8c8d'        // Gray
  },
  
  // Thresholds & Labels
  logic: {
    speedThreshold: 80,
    doffingSoonThreshold: 10,
    staleDataThreshold: 86400, // Seconds (24 hours)
    labels: {
      commError: 'COMM',
      stopped: 'STOP',
      doffing: 'DOFF',
      runningGood: 'RUN',
      noData: 'OFF'
    }
  }
}
