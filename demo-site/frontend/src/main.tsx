import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ThemeProvider } from './context/ThemeContext.tsx'

// Ensure every fetch carries the session cookie. Centralizing this here means
// existing fetch() callsites don't have to opt in individually.
const _origFetch = window.fetch.bind(window)
window.fetch = (input: RequestInfo | URL, init: RequestInit = {}) =>
  _origFetch(input, { credentials: 'include', ...init })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </StrictMode>,
)
