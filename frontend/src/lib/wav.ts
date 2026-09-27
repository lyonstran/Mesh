// Muse Voice Transcribe accepts only WAV with mono 16 or 24 kHz integer PCM (docs/muse-api.md), but browsers record
// WebM/Opus (Chrome, Android) or MP4/AAC (Safari, iOS). Decode the recording and re-encode it here, so the server
// needs no ffmpeg.

const TARGET_RATE = 16_000

/** 16-bit little-endian mono PCM in a 44-byte RIFF/WAVE header. */
export function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  const ascii = (offset: number, text: string) => [...text].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)))
  ascii(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  ascii(8, 'WAVE')
  ascii(12, 'fmt ')
  view.setUint32(16, 16, true) // fmt chunk size
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true) // byte rate
  view.setUint16(32, 2, true) // block align
  view.setUint16(34, 16, true) // bits per sample
  ascii(36, 'data')
  view.setUint32(40, samples.length * 2, true)
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return new Blob([buffer], { type: 'audio/wav' })
}

/** Any recording the browser can decode → 16 kHz mono WAV. An OfflineAudioContext resamples and downmixes. */
export async function toWav16kMono(recording: Blob): Promise<Blob> {
  const ctx = new AudioContext()
  let decoded: AudioBuffer
  try {
    decoded = await ctx.decodeAudioData(await recording.arrayBuffer())
  } finally {
    void ctx.close()
  }
  const offline = new OfflineAudioContext(1, Math.max(1, Math.ceil(decoded.duration * TARGET_RATE)), TARGET_RATE)
  const source = offline.createBufferSource()
  source.buffer = decoded
  source.connect(offline.destination)
  source.start()
  const rendered = await offline.startRendering()
  return encodeWav(rendered.getChannelData(0), TARGET_RATE)
}
