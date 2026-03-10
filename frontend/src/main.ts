import { createApp } from 'vue'
import { createPinia } from 'pinia'
import * as Sentry from '@sentry/vue'
import App from './App.vue'
import router from './router'
import './style.css'
import { maskPhone, maskName, maskSlug } from '@/directives/inputMasks'

const app = createApp(App)

const sentryDsn = import.meta.env.VITE_SENTRY_DSN
if (sentryDsn) {
  Sentry.init({
    app,
    dsn: sentryDsn,
    integrations: [
      Sentry.browserTracingIntegration({ router }),
    ],
    tracesSampleRate: 0.1,
    environment: import.meta.env.VITE_APP_ENV || 'development',
    release: 'yoohoo-frontend@1.0.0',
  })
}

app.directive('mask-phone', maskPhone)
app.directive('mask-name', maskName)
app.directive('mask-slug', maskSlug)

app.use(createPinia())
app.use(router)

app.mount('#app')
