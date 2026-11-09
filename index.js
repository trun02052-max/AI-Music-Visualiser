const express = require('express')
const multer = require('multer')
const fs = require('fs')
const path = require('path')
const axios = require('axios')
const FormData = require('form-data')

const app = express()
const PORT = process.env.PORT || 3000
const PYTHON_URL = process.env.PYTHON_URL || 'http://localhost:8000/analyze'
const COLAB_URL = process.env.COLAB_URL || 'http://localhost:8888'
const ROUTER_SCRIPT = path.join(__dirname, 'run_router.py')

app.set('view engine', 'ejs')
app.set('views', path.join(__dirname, 'views'))

const upload = multer({ dest: 'uploads/' })
const formParser = multer().none()

app.use(express.static(path.join(__dirname, 'public')))
app.use('/visual', express.static(path.join(__dirname, 'visual-engine/dist')))

const uploadStore = new Map()

function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

app.get('/', (req, res) => {
  res.render('upload')
})

app.post('/upload', upload.single('audio'), async (req, res) => {
  if (!req.file) {
    return res.status(400).send('No file uploaded')
  }

  const filePath = req.file.path
  const originalName = req.file.originalname
  const size = req.file.size
  const id = generateId()

  uploadStore.set(id, {
    path: filePath,
    originalName,
    size,
    mimetype: req.file.mimetype
  })

  try {
    const form = new FormData()
    form.append('file', fs.createReadStream(filePath), {
      filename: originalName,
      contentType: req.file.mimetype
    })

    const response = await axios.post(PYTHON_URL, form, {
      headers: form.getHeaders(),
      maxBodyLength: Infinity,
      maxContentLength: Infinity
    })

    const analysis = response.data

    uploadStore.set(id, {
      path: filePath,
      originalName,
      size,
      mimetype: req.file.mimetype,
      analysis: analysis
    })

    // --- NEW: forward culled analysis through the LLM router (Google GenAI -> OpenRouter) ---
    let visualJson = null
    if (analysis?.culled_analysis) {
      try {
        const { execSync } = require('child_process')
        const input = JSON.stringify(analysis.culled_analysis)
        const output = execSync(
          `python "${ROUTER_SCRIPT}"`,
          {
            input,
            encoding: 'utf-8',
            timeout: 60000,
            env: { ...process.env },
            maxBuffer: 10 * 1024 * 1024
          }
        ).trim()
        visualJson = JSON.parse(output)
        console.log('[Router] Visual JSON generated successfully.')
      } catch (routerErr) {
        console.error('[Router] Failed to generate visual JSON:', routerErr.message)
        if (routerErr.stderr) {
          console.error('[Router] stderr:', routerErr.stderr.toString().slice(-500))
        }
        // Non-fatal: continue without visuals
      }
    } else {
      console.log('[Router] No culled_analysis in response; skipping router.')
      console.log('[Router] Analysis keys:', analysis ? Object.keys(analysis) : 'no analysis')
    }

    const info = {
      id,
      filename: originalName,
      size: size,
      mimetype: req.file.mimetype,
      bytesRead: parseInt(req.file.size, 10),
      analysis: analysis,
      colabUrl: COLAB_URL,
      visualJson: visualJson
    }

    res.render('result', { file: info })
  } catch (err) {
    const detail = (err.response?.data?.detail || err.response?.data?.error || err.message || 'Unknown error').toString()
    console.error('Python analysis error:', detail)
    console.error('Full error:', JSON.stringify(err.toJSON ? err.toJSON() : err, null, 2))
    res.status(500).send('Error analyzing audio: ' + detail)
  }
})

app.post('/separate', formParser, async (req, res) => {
  const { id, colab_url } = req.body

  if (!id) {
    return res.status(400).json({ error: 'Missing upload id' })
  }

  const record = uploadStore.get(id)
  if (!record) {
    return res.status(404).json({ error: 'Upload not found' })
  }

  const activeColabUrl = (colab_url || COLAB_URL || '').trim().replace(/\/+$/, '')
  if (!activeColabUrl) {
    return res.status(500).json({ error: 'COLAB_URL not configured' })
  }

  console.log(`[Colab Forward] Sending request to target URL: ${activeColabUrl}`)

  try {
    const form = new FormData()
    form.append('audio_file', fs.createReadStream(record.path), {
      filename: record.originalName,
      contentType: record.mimetype
    })

    const commonHeaders = {
      'ngrok-skip-browser-warning': 'true',
      'X-Tunnel-Skip-Anti-Phishing-Page': 'true'
    }

    console.log(`[Colab Forward] Step 1: Sending analysed features to ${activeColabUrl}/analysed-features...`)
    await axios.post(`${activeColabUrl}/analysed-features`, record.analysis?.culled_analysis || {}, {
      headers: { ...commonHeaders, 'Content-Type': 'application/json' },
      timeout: 60000
    })
    console.log(`[Colab Forward] Step 1 Complete. Features received by Colab.`)

    console.log(`[Colab Forward] Step 2: Uploading audio file to ${activeColabUrl}/upload-audio...`)
    await axios.post(`${activeColabUrl}/upload-audio`, form, {
      headers: { ...commonHeaders, ...form.getHeaders() },
      maxBodyLength: Infinity,
      maxContentLength: Infinity,
      timeout: 600000
    })
    console.log(`[Colab Forward] Step 2 Complete. Audio received by Colab.`)

    res.json({ success: true, message: 'Audio and culled analysis forwarded to Colab.' })
  } catch (err) {
    const errorDetail = err.response?.data?.error || err.message
    console.error(`[Colab Forward Error] Target: ${activeColabUrl} - Message: ${errorDetail}`)
    res.status(500).json({ error: 'Forward failed: ' + errorDetail })
  }
})

app.listen(PORT, () => {
  console.log(`NodeJS server running on http://localhost:${PORT}`)
  if (!COLAB_URL) {
    console.log('COLAB_URL not set. Stem separation disabled.')
  } else {
    console.log(`Stem separation enabled via ${COLAB_URL}`)
  }
})
