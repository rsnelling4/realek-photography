import { useMemo, useState } from 'react'
import { photos } from '../data/gallery'
import Lightbox from './Lightbox'

const categories = ['All', 'Family', 'Little Ones', 'Couples', 'Weddings', 'Seniors', 'Portraits']
const PAGE_SIZE = 12

// Deal photos out one category at a time so the "All" view opens with variety
// instead of a wall of one session type.
const interleaved = (() => {
  const groups = categories.slice(1).map((cat) => photos.filter((p) => p.category === cat))
  const out = []
  for (let i = 0; out.length < photos.length; i++) {
    groups.forEach((g) => g[i] && out.push(g[i]))
  }
  return out
})()

export default function Portfolio() {
  const [active, setActive] = useState('All')
  const [visible, setVisible] = useState(PAGE_SIZE)
  const [openIndex, setOpenIndex] = useState(null)

  const filtered = useMemo(
    () => (active === 'All' ? interleaved : photos.filter((p) => p.category === active)),
    [active]
  )
  const shown = filtered.slice(0, visible)

  const selectCategory = (cat) => {
    setActive(cat)
    setVisible(PAGE_SIZE)
  }

  return (
    <section id="portfolio" className="py-24 px-6 bg-cream">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <p className="section-label">My Work</p>
          <h2 className="section-heading">
            Stories Worth<br />
            <em>Remembering</em>
          </h2>
          <p className="mt-4 text-taupe font-sans font-light text-lg max-w-md mx-auto">
            Each portrait is a collaboration — a quiet conversation between
            photographer and subject.
          </p>
        </div>

        {/* Filter tabs */}
        <div className="flex justify-center gap-2 mb-12 flex-wrap">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => selectCategory(cat)}
              aria-pressed={active === cat}
              className={`font-sans text-xs font-medium tracking-widest uppercase px-5 py-2.5 transition-all duration-200 ${
                active === cat
                  ? 'bg-terracotta text-cream'
                  : 'border border-dark-brown/20 text-taupe hover:border-terracotta hover:text-terracotta'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Grid */}
        <div className="columns-2 md:columns-3 gap-3 md:gap-4 space-y-3 md:space-y-4">
          {shown.map((photo, i) => (
            <button
              key={photo.src}
              onClick={() => setOpenIndex(i)}
              aria-label={`View larger: ${photo.alt}`}
              className="block w-full break-inside-avoid overflow-hidden group relative bg-parchment"
            >
              <img
                src={photo.thumb}
                alt={photo.alt}
                width={photo.w}
                height={photo.h}
                loading="lazy"
                decoding="async"
                className="w-full h-auto transition-transform duration-700 group-hover:scale-105"
              />
              <span className="absolute inset-0 bg-dark-brown/0 group-hover:bg-dark-brown/25 transition-colors duration-300 flex items-end p-4">
                <span className="font-sans text-[10px] tracking-widest uppercase text-cream opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                  {photo.category}
                </span>
              </span>
            </button>
          ))}
        </div>

        <div className="text-center mt-12 flex flex-col sm:flex-row gap-4 justify-center">
          {visible < filtered.length && (
            <button onClick={() => setVisible(visible + PAGE_SIZE)} className="btn-outline">
              Show More ({filtered.length - visible})
            </button>
          )}
          <a href="#contact" className="btn-primary">
            Book Your Session
          </a>
        </div>
      </div>

      {openIndex !== null && (
        <Lightbox
          photos={filtered}
          index={openIndex}
          onChange={setOpenIndex}
          onClose={() => setOpenIndex(null)}
        />
      )}
    </section>
  )
}
