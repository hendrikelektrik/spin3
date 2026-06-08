<template>
  <div class="layout-container">
    <aside class="sidebar" :class="{ 'collapsed': isCollapsed }">
      <div class="sidebar-header">
        <h2 v-if="!isCollapsed">Spin3 Ringframe</h2>
        <button @click="isCollapsed = !isCollapsed" class="toggle-btn">
          {{ isCollapsed ? '→' : '←' }}
        </button>
      </div>
      
      <nav class="nav-menu">
        <div class="nav-label" v-if="!isCollapsed">SPIN3 PROJECT</div>
        
        <router-link to="/spin3/status" class="nav-item" active-class="active">
          <span class="icon">📊</span>
          <span v-if="!isCollapsed">Real-time Status</span>
        </router-link>

        <router-link to="/spin3/history" class="nav-item" active-class="active">
          <span class="icon">⏳</span>
          <span v-if="!isCollapsed">Status Timeline</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <button @click="handleLogout" class="logout-btn">
          <span class="icon">🚪</span>
          <span v-if="!isCollapsed">Logout</span>
        </button>
      </div>
    </aside>

    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const isCollapsed = ref(false)
const auth = useAuthStore()
const router = useRouter()

const handleLogout = () => {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.layout-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

.sidebar {
  width: 240px;
  background: #2c3e50;
  color: white;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  flex-shrink: 0;
}

.sidebar.collapsed {
  width: 60px;
}

.sidebar-header {
  padding: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}

.sidebar-header h2 {
  margin: 0;
  font-size: 1.2rem;
}

.toggle-btn {
  background: transparent;
  border: none;
  color: white;
  cursor: pointer;
  padding: 5px;
}

.nav-menu {
  flex-grow: 1;
  padding: 15px 0;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  text-decoration: none;
  color: #bdc3c7;
  transition: all 0.2s;
}

.nav-item:hover {
  background: rgba(255,255,255,0.1);
  color: white;
}

.nav-item.active {
  background: #42b983;
  color: white;
}

.nav-item.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.icon {
  margin-right: 15px;
  font-size: 1.2rem;
}

.collapsed .icon {
  margin-right: 0;
}

.nav-divider {
  height: 1px;
  background: rgba(255,255,255,0.1);
  margin: 15px 0;
}

.nav-label {
  padding: 0 20px;
  font-size: 0.7rem;
  color: #7f8c8d;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.sidebar-footer {
  padding: 20px;
  border-top: 1px solid rgba(255,255,255,0.1);
}

.logout-btn {
  width: 100%;
  background: #e74c3c;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.collapsed .logout-btn {
  padding: 10px 0;
}

.main-content {
  flex-grow: 1;
  overflow-y: auto;
  background: #f8f9fa;
}
</style>
