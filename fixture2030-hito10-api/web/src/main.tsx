import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/plus-jakarta-sans/400.css'
import '@fontsource/plus-jakarta-sans/500.css'
import '@fontsource/plus-jakarta-sans/600.css'
import '@fontsource/plus-jakarta-sans/700.css'
import '@fontsource/plus-jakarta-sans/800.css'
import './styles/tokens.css'
import './styles/app.css'
import './styles/fixture.css'
import { App } from './App'

const root = document.getElementById('root')
if (!root) throw new Error('Falta #root en index.html')

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
