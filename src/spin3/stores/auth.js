import { defineStore } from 'pinia'
import axios from 'axios'

const API_BASE_URL = `http://${window.location.hostname}:8000`

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('user')) || null,
  }),
  actions: {
    async login(username, password) {
      try {
        console.log(`Attempting login for ${username} at ${API_BASE_URL}/spin3/login`);
        const response = await axios.post(`${API_BASE_URL}/spin3/login`, {
          username,
          password
        })
        
        console.log('Login response:', response.data);
        if (response.data && !response.data.error) {
          const user = response.data
          this.user = user
          localStorage.setItem('user', JSON.stringify(user))
          return true
        }
        return false
      } catch (error) {
        if (error.response) {
          // The server responded with a status code outside the range of 2xx
          console.error('Login error response:', error.response.status, error.response.data);
        } else if (error.request) {
          // The request was made but no response was received
          console.error('Login error: No response from server. Is the backend running at localhost:8000?');
        } else {
          console.error('Login error message:', error.message);
        }
        return false
      }
    },
    logout() {
      this.user = null
      localStorage.removeItem('user')
    }
  },
  getters: {
    isAuthenticated: (state) => !!state.user,
  }
})
