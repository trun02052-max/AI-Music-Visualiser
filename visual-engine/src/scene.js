import * as THREE from 'three'
import { createObject } from './objects.js'
import { createPostProcessing } from './effects.js'
import { applyMotion, updateParticles, updateWave } from './motions.js'
import { validateScene } from './schema.js'

// Valid hex color: # followed by 6 hex digits
const _HEX_RE = /^#([0-9a-fA-F]{6})$/

function _fixColor(c) {
  if (typeof c !== 'string') return '#ffffff'
  const m = c.trim().match(_HEX_RE)
  if (m) return '#' + m[1].toUpperCase()
  // Try to salvage: strip non-hex chars, take first 6
  const cleaned = c.trim().replace(/[^0-9a-fA-F]/g, '')
  if (cleaned.length >= 6) return '#' + cleaned.slice(0, 6).toUpperCase()
  console.warn('Invalid color, falling back to white:', c)
  return '#ffffff'
}

export function buildScene(container, sceneData) {
  const errors = validateScene(sceneData)
  if (errors.length > 0) {
    console.error('Scene validation errors:', errors)
    return null
  }

  const scene = new THREE.Scene()

  if (sceneData.background) {
    if (sceneData.background.gradient && sceneData.background.gradient.length >= 2) {
      const canvas = document.createElement('canvas')
      canvas.width = 2
      canvas.height = 256
      const ctx = canvas.getContext('2d')
      const gradient = ctx.createLinearGradient(0, 0, 0, 256)
      gradient.addColorStop(0, _fixColor(sceneData.background.gradient[0]))
      gradient.addColorStop(1, _fixColor(sceneData.background.gradient[1]))
      ctx.fillStyle = gradient
      ctx.fillRect(0, 0, 2, 256)
      const texture = new THREE.CanvasTexture(canvas)
      scene.background = texture
    } else if (sceneData.background.color) {
      scene.background = new THREE.Color(_fixColor(sceneData.background.color))
    }
  }

  const camera = new THREE.PerspectiveCamera(
    sceneData.camera?.fov || 75,
    container.clientWidth / container.clientHeight,
    0.1,
    1000
  )
  camera.position.set(...(sceneData.camera?.position || [0, 0, 10]))
  if (sceneData.camera?.lookAt) {
    camera.lookAt(new THREE.Vector3(...sceneData.camera.lookAt))
  }

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setSize(container.clientWidth, container.clientHeight)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  container.appendChild(renderer.domElement)

  const composer = createPostProcessing(renderer, scene, camera, sceneData.effects || {})

  if (sceneData.lighting) {
    for (const light of sceneData.lighting) {
      let THREE_light
      const color = new THREE.Color(_fixColor(light.color || '#ffffff'))
      const intensity = light.intensity || 1

      switch (light.type) {
        case 'ambient':
          THREE_light = new THREE.AmbientLight(color, intensity)
          break
        case 'directional':
          THREE_light = new THREE.DirectionalLight(color, intensity)
          THREE_light.position.set(...(light.position || [5, 10, 7]))
          break
        case 'point':
          THREE_light = new THREE.PointLight(color, intensity, 50)
          THREE_light.position.set(...(light.position || [0, 5, 0]))
          break
        case 'spot':
          THREE_light = new THREE.SpotLight(color, intensity, 50, Math.PI / 6)
          THREE_light.position.set(...(light.position || [0, 10, 0]))
          break
        case 'emissive':
          THREE_light = new THREE.PointLight(color, intensity * 2, 30)
          THREE_light.position.set(...(light.position || [0, 0, 0]))
          break
      }

      if (THREE_light) {
        scene.add(THREE_light)
      }
    }
  }

  const objects = []
  for (const objData of sceneData.objects || []) {
    const obj = createObject(objData)
    obj.userData = { ...objData, startTime: objData.startTime || 0, endTime: objData.endTime || Infinity }
    scene.add(obj)
    objects.push(obj)
  }

  const clock = new THREE.Clock()
  const timeScale = sceneData.global?.timeScale || 1
  const loop = sceneData.global?.loop !== false
  const duration = sceneData.global?.duration || 30

  function animate() {
    requestAnimationFrame(animate)

    const elapsed = clock.getElapsedTime() * timeScale
    const deltaTime = clock.getDelta() * timeScale

    if (!loop && elapsed > duration) {
      return
    }

    for (const obj of objects) {
      const { startTime, endTime, motion } = obj.userData
      if (elapsed >= startTime && elapsed <= endTime) {
        applyMotion(obj, motion, elapsed, deltaTime)

        if (obj.userData.type === 'particles') {
          updateParticles(obj.geometry, motion, elapsed, obj.userData)
        } else if (obj.userData.type === 'wave') {
          updateWave(obj.geometry, elapsed, obj.userData)
        }
      }
    }

    if (sceneData.effects?.kaleidoscope?.enabled && composer.passes.length > 0) {
      const kaleidoPass = composer.passes.find(p => p.uniforms && p.uniforms.slices)
      if (kaleidoPass) {
        kaleidoPass.uniforms.angle.value = elapsed * 0.2
      }
    }

    if (sceneData.effects?.glitch?.enabled && composer.passes.length > 0) {
      const glitchPass = composer.passes.find(p => p.uniforms && p.uniforms.time)
      if (glitchPass) {
        glitchPass.uniforms.time.value = elapsed
      }
    }

    composer.render()
  }

  animate()

  window.addEventListener('resize', () => {
    camera.aspect = container.clientWidth / container.clientHeight
    camera.updateProjectionMatrix()
    renderer.setSize(container.clientWidth, container.clientHeight)
    composer.setSize(container.clientWidth, container.clientHeight)
  })

  return { scene, camera, renderer, composer, objects }
}
