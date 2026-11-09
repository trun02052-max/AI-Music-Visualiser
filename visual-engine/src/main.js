import * as THREE from 'three'
import { buildScene } from './scene.js'

let sceneData = null
let sceneInstance = null

async function loadScene(url) {
  try {
    const res = await fetch(url)
    sceneData = await res.json()
    return sceneData
  } catch (e) {
    console.error('Failed to load scene:', e)
    return null
  }
}

function init(containerId, sceneDataOrUrl) {
  const container = document.getElementById(containerId)
  if (!container) {
    console.error('Container not found:', containerId)
    return
  }

  let data = sceneDataOrUrl
  if (typeof sceneDataOrUrl === 'string') {
    data = null
    fetch(sceneDataOrUrl).then(r => r.json()).then(d => {
      if (d) {
        sceneInstance = buildScene(container, d)
      }
    })
  }

  if (data) {
    sceneInstance = buildScene(container, data)
  }

  return sceneInstance
}

export { init, loadScene }
window.visualEngine = init
window.loadVisualScene = loadScene

console.log('Visual engine module loaded, window.visualEngine set:', typeof window.visualEngine)
