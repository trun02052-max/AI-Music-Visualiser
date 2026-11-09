const SCENE_SCHEMA = {
  type: 'object',
  required: ['objects'],
  properties: {
    background: {
      type: 'object',
      properties: {
        color: { type: 'string' },
        gradient: { type: 'array', items: { type: 'string' } }
      }
    },
    camera: {
      type: 'object',
      properties: {
        fov: { type: 'number' },
        position: { type: 'array', items: { type: 'number' }, minItems: 3, maxItems: 3 },
        lookAt: { type: 'array', items: { type: 'number' }, minItems: 3, maxItems: 3 }
      }
    },
    lighting: {
      type: 'array',
      items: {
        type: 'object',
        required: ['type'],
        properties: {
          type: { type: 'string', enum: ['ambient', 'directional', 'point', 'spot', 'emissive'] },
          color: { type: 'string' },
          intensity: { type: 'number' },
          position: { type: 'array', items: { type: 'number' }, minItems: 3, maxItems: 3 },
          target: { type: 'array', items: { type: 'number' }, minItems: 3, maxItems: 3 }
        }
      }
    },
    objects: {
      type: 'array',
      items: {
        type: 'object',
        required: ['type', 'id'],
        properties: {
          type: { type: 'string', enum: ['particles', 'ring', 'circle', 'wave', 'line', 'box', 'sphere', 'torus', 'cone', 'cylinder', 'stars', 'fog', 'mesh'] },
          id: { type: 'string' },
          count: { type: 'number' },
          position: { type: 'array', items: { type: 'number' }, minItems: 3, maxItems: 3 },
          rotation: { type: 'array', items: { type: 'number' }, minItems: 3, maxItems: 3 },
          scale: { type: 'array', items: { type: 'number' }, minItems: 3, maxItems: 3 },
          color: { type: 'string' },
          colors: { type: 'array', items: { type: 'string' } },
          opacity: { type: 'number', minimum: 0, maximum: 1 },
          size: { type: 'number' },
          radius: { type: 'number' },
          tubeRadius: { type: 'number' },
          innerRadius: { type: 'number' },
          outerRadius: { type: 'number' },
          width: { type: 'number' },
          height: { type: 'number' },
          depth: { type: 'number' },
          radialSegments: { type: 'number' },
          tubularSegments: { type: 'number' },
          points: { type: 'array' },
          motion: {
            type: 'object',
            properties: {
              type: { type: 'string', enum: ['move', 'rotate', 'orbit', 'float', 'fall', 'rise', 'expand', 'contract', 'swarm', 'explode', 'implode', 'wave', 'shake', 'pulse'] },
              speed: { type: 'number' },
              amplitude: { type: 'number' },
              frequency: { type: 'number' },
              axis: { type: 'string', enum: ['x', 'y', 'z'] },
              center: { type: 'array', items: { type: 'number' }, minItems: 3, maxItems: 3 },
              target: { type: 'array', items: { type: 'number' }, minItems: 3, maxItems: 3 }
            }
          },
          startTime: { type: 'number' },
          endTime: { type: 'number' }
        }
      }
    },
    effects: {
      type: 'object',
      properties: {
        bloom: {
          type: 'object',
          properties: {
            enabled: { type: 'boolean' },
            strength: { type: 'number' },
            radius: { type: 'number' },
            threshold: { type: 'number' }
          }
        },
        chromaticAberration: {
          type: 'object',
          properties: {
            enabled: { type: 'boolean' },
            offset: { type: 'number' }
          }
        },
        vignette: {
          type: 'object',
          properties: {
            enabled: { type: 'boolean' },
            offset: { type: 'number' },
            darkness: { type: 'number' }
          }
        },
        kaleidoscope: {
          type: 'object',
          properties: {
            enabled: { type: 'boolean' },
            slices: { type: 'number' }
          }
        },
        glitch: {
          type: 'object',
          properties: {
            enabled: { type: 'boolean' },
            intensity: { type: 'number' }
          }
        }
      }
    },
    global: {
      type: 'object',
      properties: {
        timeScale: { type: 'number' },
        loop: { type: 'boolean' },
        duration: { type: 'number' }
      }
    }
  }
}

export function validateScene(data) {
  const errors = []
  
  if (!data.objects || !Array.isArray(data.objects)) {
    errors.push('Scene must have an objects array')
    return errors
  }

  for (const obj of data.objects) {
    if (!obj.type) {
      errors.push(`Object missing type: ${JSON.stringify(obj)}`)
    }
    if (!obj.id) {
      errors.push(`Object missing id: ${JSON.stringify(obj)}`)
    }
  }

  return errors
}

export { SCENE_SCHEMA }
