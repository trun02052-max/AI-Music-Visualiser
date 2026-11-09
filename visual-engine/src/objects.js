import * as THREE from 'three'

export function createParticles(opts) {
  const count = opts.count || 1000
  const geometry = new THREE.BufferGeometry()
  const positions = new Float32Array(count * 3)
  const colors = new Float32Array(count * 3)

  const color = new THREE.Color(opts.color || '#ffffff')
  const colorsArr = opts.colors || [opts.color]

  for (let i = 0; i < count; i++) {
    positions[i * 3] = (Math.random() - 0.5) * (opts.size || 10)
    positions[i * 3 + 1] = (Math.random() - 0.5) * (opts.size || 10)
    positions[i * 3 + 2] = (Math.random() - 0.5) * (opts.size || 10)

    const c = new THREE.Color(colorsArr[Math.floor(Math.random() * colorsArr.length)])
    colors[i * 3] = c.r
    colors[i * 3 + 1] = c.g
    colors[i * 3 + 2] = c.b
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

  const material = new THREE.PointsMaterial({
    size: opts.pointSize || 0.05,
    vertexColors: true,
    transparent: true,
    opacity: opts.opacity ?? 1,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  })

  const mesh = new THREE.Points(geometry, material)
  mesh.position.set(...(opts.position || [0, 0, 0]))
  return mesh
}

export function createRing(opts) {
  const geometry = new THREE.TorusGeometry(opts.radius || 1, opts.tubeRadius || 0.1, opts.radialSegments || 16, opts.tubularSegments || 100)
  const material = new THREE.MeshStandardMaterial({
    color: new THREE.Color(opts.color || '#ff00ff'),
    emissive: new THREE.Color(opts.color || '#ff00ff'),
    emissiveIntensity: 0.5,
    metalness: 0.8,
    roughness: 0.2,
    transparent: true,
    opacity: opts.opacity ?? 1
  })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.position.set(...(opts.position || [0, 0, 0]))
  return mesh
}

export function createCircle(opts) {
  const geometry = new THREE.CircleGeometry(opts.radius || 1, opts.radialSegments || 64)
  const material = new THREE.MeshBasicMaterial({
    color: new THREE.Color(opts.color || '#00ffff'),
    transparent: true,
    opacity: opts.opacity ?? 1,
    side: THREE.DoubleSide
  })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.position.set(...(opts.position || [0, 0, 0]))
  return mesh
}

export function createWave(opts) {
  const geometry = new THREE.PlaneGeometry(opts.width || 10, opts.height || 10, 128, 128)
  const material = new THREE.MeshStandardMaterial({
    color: new THREE.Color(opts.color || '#ff00ff'),
    wireframe: opts.wireframe || false,
    metalness: 0.5,
    roughness: 0.5,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: opts.opacity ?? 1
  })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.rotation.x = -Math.PI / 2
  mesh.position.set(...(opts.position || [0, 0, 0]))
  return mesh
}

export function createLine(opts) {
  const points = opts.points || [[-5, 0, 0], [5, 0, 0]]
  const geometry = new THREE.BufferGeometry().setFromPoints(
    points.map(p => new THREE.Vector3(...p))
  )
  const material = new THREE.LineBasicMaterial({
    color: new THREE.Color(opts.color || '#ffffff'),
    transparent: true,
    opacity: opts.opacity ?? 1
  })
  const line = new THREE.Line(geometry, material)
  line.position.set(...(opts.position || [0, 0, 0]))
  return line
}

export function createBox(opts) {
  const geometry = new THREE.BoxGeometry(opts.width || 1, opts.height || 1, opts.depth || 1)
  const material = new THREE.MeshStandardMaterial({
    color: new THREE.Color(opts.color || '#ff00ff'),
    emissive: new THREE.Color(opts.color || '#ff00ff'),
    emissiveIntensity: 0.3,
    metalness: 0.7,
    roughness: 0.3,
    transparent: true,
    opacity: opts.opacity ?? 1
  })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.position.set(...(opts.position || [0, 0, 0]))
  return mesh
}

export function createSphere(opts) {
  const geometry = new THREE.SphereGeometry(opts.radius || 1, opts.radialSegments || 32, 16)
  const material = new THREE.MeshStandardMaterial({
    color: new THREE.Color(opts.color || '#00ffff'),
    emissive: new THREE.Color(opts.color || '#00ffff'),
    emissiveIntensity: 0.3,
    metalness: 0.7,
    roughness: 0.3,
    transparent: true,
    opacity: opts.opacity ?? 1
  })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.position.set(...(opts.position || [0, 0, 0]))
  return mesh
}

export function createTorus(opts) {
  const geometry = new THREE.TorusKnotGeometry(opts.radius || 1, opts.tubeRadius || 0.3, 100, 16)
  const material = new THREE.MeshStandardMaterial({
    color: new THREE.Color(opts.color || '#ff00ff'),
    emissive: new THREE.Color(opts.color || '#ff00ff'),
    emissiveIntensity: 0.4,
    metalness: 0.8,
    roughness: 0.2,
    transparent: true,
    opacity: opts.opacity ?? 1
  })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.position.set(...(opts.position || [0, 0, 0]))
  return mesh
}

export function createCone(opts) {
  const geometry = new THREE.ConeGeometry(opts.radius || 1, opts.height || 2, opts.radialSegments || 32)
  const material = new THREE.MeshStandardMaterial({
    color: new THREE.Color(opts.color || '#ffff00'),
    emissive: new THREE.Color(opts.color || '#ffff00'),
    emissiveIntensity: 0.3,
    metalness: 0.7,
    roughness: 0.3,
    transparent: true,
    opacity: opts.opacity ?? 1
  })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.position.set(...(opts.position || [0, 0, 0]))
  return mesh
}

export function createStars(opts) {
  const count = opts.count || 500
  const geometry = new THREE.BufferGeometry()
  const positions = new Float32Array(count * 3)
  const colors = new Float32Array(count * 3)

  for (let i = 0; i < count; i++) {
    const r = 50 + Math.random() * 100
    const theta = Math.random() * Math.PI * 2
    const phi = Math.acos(2 * Math.random() - 1)
    positions[i * 3] = r * Math.sin(phi) * Math.cos(theta)
    positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
    positions[i * 3 + 2] = r * Math.cos(phi)

    const brightness = 0.5 + Math.random() * 0.5
    colors[i * 3] = brightness
    colors[i * 3 + 1] = brightness
    colors[i * 3 + 2] = brightness
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

  const material = new THREE.PointsMaterial({
    size: 0.5,
    vertexColors: true,
    transparent: true,
    opacity: opts.opacity ?? 1,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  })

  const mesh = new THREE.Points(geometry, material)
  mesh.position.set(...(opts.position || [0, 0, 0]))
  return mesh
}

export function createFog(opts) {
  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(opts.radius || 20, 32, 32),
    new THREE.MeshBasicMaterial({
      color: new THREE.Color(opts.color || '#0000ff'),
      transparent: true,
      opacity: opts.opacity ?? 0.3,
      side: THREE.BackSide,
      depthWrite: false
    })
  )
  mesh.position.set(...(opts.position || [0, 0, 0]))
  return mesh
}

export function createObject(opts) {
  switch (opts.type) {
    case 'particles': return createParticles(opts)
    case 'ring': return createRing(opts)
    case 'circle': return createCircle(opts)
    case 'wave': return createWave(opts)
    case 'line': return createLine(opts)
    case 'box': return createBox(opts)
    case 'sphere': return createSphere(opts)
    case 'torus': return createTorus(opts)
    case 'cone': return createCone(opts)
    case 'stars': return createStars(opts)
    case 'fog': return createFog(opts)
    default: return createSphere(opts)
  }
}
