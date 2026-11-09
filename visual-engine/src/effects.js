import * as THREE from 'three'
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js'
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js'
import { RGBShiftShader } from 'three/addons/shaders/RGBShiftShader.js'

const KaleidoscopeShader = {
  uniforms: {
    tDiffuse: { value: null },
    slices: { value: 6.0 },
    angle: { value: 0.0 }
  },
  vertexShader: `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: `
    uniform sampler2D tDiffuse;
    uniform float slices;
    uniform float angle;
    varying vec2 vUv;
    void main() {
      vec2 centered = vUv - 0.5;
      float r = length(centered);
      float a = atan(centered.y, centered.x) + angle;
      a = mod(a, 2.0 * 3.14159 / slices);
      a = abs(a - 3.14159 / slices);
      vec2 newUv = 0.5 + r * vec2(cos(a), sin(a));
      gl_FragColor = texture2D(tDiffuse, newUv);
    }
  `
}

const VignetteShader = {
  uniforms: {
    tDiffuse: { value: null },
    offset: { value: 1.0 },
    darkness: { value: 1.0 }
  },
  vertexShader: `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: `
    uniform sampler2D tDiffuse;
    uniform float offset;
    uniform float darkness;
    varying vec2 vUv;
    void main() {
      vec4 color = texture2D(tDiffuse, vUv);
      vec2 centered = vUv - 0.5;
      float dist = length(centered);
      float vignette = smoothstep(offset, offset * 0.5, dist);
      color.rgb *= mix(1.0, vignette, darkness);
      gl_FragColor = color;
    }
  `
}

const GlitchShader = {
  uniforms: {
    tDiffuse: { value: null },
    time: { value: 0.0 },
    intensity: { value: 0.1 }
  },
  vertexShader: `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: `
    uniform sampler2D tDiffuse;
    uniform float time;
    uniform float intensity;
    varying vec2 vUv;
    float random(vec2 st) {
      return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453);
    }
    void main() {
      vec2 uv = vUv;
      float glitch = step(0.9, random(vec2(floor(uv.y * 50.0), floor(time * 10.0))));
      uv.x += glitch * intensity * (random(vec2(time, uv.y)) - 0.5);
      gl_FragColor = texture2D(tDiffuse, uv);
    }
  `
}

export function createPostProcessing(renderer, scene, camera, effects) {
  const composer = new EffectComposer(renderer)
  const renderPass = new RenderPass(scene, camera)
  composer.addPass(renderPass)

  try {
    if (effects.bloom?.enabled !== false) {
      const bloomPass = new UnrealBloomPass(
        new THREE.Vector2(window.innerWidth, window.innerHeight),
        effects.bloom?.strength || 1.5,
        effects.bloom?.radius || 0.4,
        effects.bloom?.threshold || 0.1
      )
      composer.addPass(bloomPass)
    }
  } catch (e) {
    console.error('Bloom pass failed:', e)
  }

  try {
    if (effects.chromaticAberration?.enabled) {
      const rgbShift = new ShaderPass(RGBShiftShader)
      if (rgbShift.uniforms?.offset) {
        rgbShift.uniforms.offset.value = effects.chromaticAberration.offset || 0.002
      }
      composer.addPass(rgbShift)
    }
  } catch (e) {
    console.error('Chromatic aberration pass failed:', e)
  }

  try {
    if (effects.kaleidoscope?.enabled) {
      const kaleido = new ShaderPass(KaleidoscopeShader)
      if (kaleido.uniforms?.slices) {
        kaleido.uniforms.slices.value = effects.kaleidoscope.slices || 6
      }
      if (kaleido.uniforms?.angle) {
        kaleido.uniforms.angle.value = 0
      }
      composer.addPass(kaleido)
    }
  } catch (e) {
    console.error('Kaleidoscope pass failed:', e)
  }

  try {
    if (effects.vignette?.enabled !== false) {
      const vignette = new ShaderPass(VignetteShader)
      if (vignette.uniforms?.offset) {
        vignette.uniforms.offset.value = effects.vignette.offset || 0.5
      }
      if (vignette.uniforms?.darkness) {
        vignette.uniforms.darkness.value = effects.vignette.darkness || 1.0
      }
      composer.addPass(vignette)
    }
  } catch (e) {
    console.error('Vignette pass failed:', e)
  }

  try {
    if (effects.glitch?.enabled) {
      const glitch = new ShaderPass(GlitchShader)
      if (glitch.uniforms?.intensity) {
        glitch.uniforms.intensity.value = effects.glitch.intensity || 0.1
      }
      composer.addPass(glitch)
    }
  } catch (e) {
    console.error('Glitch pass failed:', e)
  }

  return composer
}
