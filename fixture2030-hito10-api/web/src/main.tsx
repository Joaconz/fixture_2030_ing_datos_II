import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/fira-sans/400.css'
import '@fontsource/fira-sans/500.css'
import '@fontsource/fira-sans/600.css'
import '@fontsource/fira-sans/700.css'
import '@fontsource/fira-code/400.css'
import '@fontsource/fira-code/500.css'
import './styles/tokens.css'
import './styles/app.css'
import { App } from './App'

const root = document.getElementById('root')
if (!root) throw new Error('Falta #root en index.html')

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
