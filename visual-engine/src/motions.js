export function applyMotion(object, motion, time, deltaTime) {
  if (!motion || !motion.type) return

  const speed = motion.speed || 1
  const t = time * speed
  const amp = motion.amplitude || 1
  const freq = motion.frequency || 1

  switch (motion.type) {
    case 'rotate':
      object.rotation[motion.axis || 'y'] += deltaTime * speed * (motion.direction || 1)
      break

    case 'orbit':
      const center = motion.center || [0, 0, 0]
      const radius = motion.radius || 5
      object.position.x = center[0] + Math.cos(t) * radius
      object.position.z = center[2] + Math.sin(t) * radius
      break

    case 'float':
      object.position.y += Math.sin(t * freq) * amp * deltaTime
      break

    case 'fall':
      object.position.y -= speed * deltaTime * 2
      if (object.position.y < -10) object.position.y = 10
      break

    case 'rise':
      object.position.y += speed * deltaTime * 2
      if (object.position.y > 10) object.position.y = -10
      break

    case 'expand':
      const expandScale = 1 + Math.sin(t * freq) * amp * 0.5
      object.scale.setScalar(Math.max(0.01, expandScale))
      break

    case 'contract':
      const contractScale = 1 - Math.sin(t * freq) * amp * 0.3
      object.scale.setScalar(Math.max(0.01, contractScale))
      break

    case 'wave':
      object.position.y = Math.sin(t * freq) * amp
      break

    case 'shake':
      object.position.x = (Math.random() - 0.5) * amp * 0.5
      object.position.y = (Math.random() - 0.5) * amp * 0.5
      object.position.z = (Math.random() - 0.5) * amp * 0.5
      break

    case 'pulse':
      const pulseScale = 1 + Math.sin(t * freq * 2) * amp * 0.2
      object.scale.setScalar(Math.max(0.01, pulseScale))
      break

    case 'move':
      if (motion.target) {
        const target = new THREE.Vector3(...motion.target)
        object.position.lerp(target, deltaTime * speed * 0.5)
      }
      break

    case 'explode':
      const explodeDir = object.position.clone().normalize()
      if (explodeDir.length() < 0.1) explodeDir.set(Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5)
      object.position.add(explodeDir.multiplyScalar(speed * deltaTime * 2))
      break

    case 'implode':
      const implodeDir = object.position.clone().normalize()
      if (implodeDir.length() > 0.1) {
        object.position.add(implodeDir.multiplyScalar(-speed * deltaTime * 2))
      }
      break

    case 'swarm':
      object.position.x += (Math.random() - 0.5) * speed * deltaTime * 2
      object.position.y += (Math.random() - 0.5) * speed * deltaTime * 2
      object.position.z += (Math.random() - 0.5) * speed * deltaTime * 2
      break

    default:
      break
  }
}

export function updateParticles(geometry, motion, time, opts) {
  if (!motion || motion.type !== 'swarm') return

  const positions = geometry.attributes.position.array
  const count = positions.length / 3
  const speed = motion.speed || 1
  const amp = motion.amplitude || 1
  const t = time * speed

  for (let i = 0; i < count; i++) {
    const i3 = i * 3
    positions[i3] += (Math.random() - 0.5) * speed * 0.1
    positions[i3 + 1] += (Math.random() - 0.5) * speed * 0.1
    positions[i3 + 2] += (Math.random() - 0.5) * speed * 0.1

    const dist = Math.sqrt(positions[i3] ** 2 + positions[i3 + 1] ** 2 + positions[i3 + 2] ** 2)
    if (dist > (opts.size || 10)) {
      positions[i3] *= -1
      positions[i3 + 1] *= -1
      positions[i3 + 2] *= -1
    }
  }
  geometry.attributes.position.needsUpdate = true
}

export function updateWave(geometry, time, opts) {
  const positions = geometry.attributes.position.array
  const width = opts.width || 10
  const height = opts.height || 10
  const freq = (opts.motion?.frequency || 1) * 0.5
  const amp = (opts.motion?.amplitude || 1) * 0.5

  for (let i = 0; i < positions.length; i += 3) {
    const x = positions[i]
    const y = positions[i + 1]
    positions[i + 2] = Math.sin(x * freq + time) * amp + Math.cos(y * freq + time) * amp
  }
  geometry.attributes.position.needsUpdate = true
}
