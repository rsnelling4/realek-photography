import { useEffect, useRef } from 'react'

export default function Lightbox({ photos, index, onClose, onChange }) {
  const touchX = useRef(null)
  const closeRef = useRef(null)
  const photo = photos[index]

  const prev = () => onChange((index - 1 + photos.length) % photos.length)
  const next = () => onChange((index + 1) % photos.length)

  // Keyboard controls + lock page scroll while open
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowLeft') prev()
      if (e.key === 'ArrowRight') next()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  useEffect(() => {
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()
    return () => { document.body.style.overflow = overflow }
  }, [])

  // Preload neighbours so arrowing through feels instant
  useEffect(() => {
    ;[index - 1, index + 1].forEach((i) => {
      const p = photos[(i + photos.length) % photos.length]
      if (p) new Image().src = p.src
    })
  }, [index, photos])

  const onTouchStart = (e) => { touchX.current = e.touches[0].clientX }
  const onTouchEnd = (e) => {
    if (touchX.current === null) return
    const dx = e.changedTouches[0].clientX - touchX.current
    if (Math.abs(dx) > 50) (dx > 0 ? prev : next)()
    touchX.current = null
  }

  const navBtn =
    'absolute top-1/2 -translate-y-1/2 w-12 h-12 flex items-center justify-center text-cream/70 hover:text-cream text-3xl transition-colors'

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Photo viewer"
      className="fixed inset-0 z-[60] bg-dark-brown/95 flex flex-col items-center justify-center gap-5 px-6"
      onClick={onClose}
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
    >
      <img
        key={photo.src}
        src={photo.src}
        alt={photo.alt}
        width={photo.w}
        height={photo.h}
        className="max-h-[75vh] max-w-full md:max-w-[80vw] w-auto h-auto object-contain shadow-2xl animate-fade-in"
        onClick={(e) => e.stopPropagation()}
      />

      <button
        ref={closeRef}
        onClick={onClose}
        aria-label="Close"
        className="absolute top-5 right-5 w-12 h-12 flex items-center justify-center text-cream/70 hover:text-cream text-3xl transition-colors"
      >
        ×
      </button>
      <button
        onClick={(e) => { e.stopPropagation(); prev() }}
        aria-label="Previous photo"
        className={`${navBtn} left-2 md:left-6`}
      >
        ‹
      </button>
      <button
        onClick={(e) => { e.stopPropagation(); next() }}
        aria-label="Next photo"
        className={`${navBtn} right-2 md:right-6`}
      >
        ›
      </button>

      <div className="flex flex-col items-center gap-3" onClick={(e) => e.stopPropagation()}>
        <p className="font-sans text-xs tracking-widest uppercase text-cream/60">
          {photo.category} · {index + 1} / {photos.length}
        </p>
        <a
          href="#contact"
          onClick={onClose}
          className="btn-primary text-xs py-2.5 px-6"
        >
          Book a Session Like This
        </a>
      </div>
    </div>
  )
}
