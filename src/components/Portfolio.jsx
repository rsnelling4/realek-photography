import { useState } from 'react'

const images = [
  { src: '1.jpg',      category: 'Family' },
  { src: '2.jpg',      category: 'Family' },
  { src: '3.jpg',      category: 'Family' },
  { src: '4.jpg',      category: 'Family' },
  { src: '5.jpg',      category: 'Family' },
  { src: '6.jpg',      category: 'Family' },
  { src: '7.jpg',      category: 'Family' },
  { src: 'grass2.jpg', category: 'Family' },
  { src: '13.jpg',     category: 'Family' },
  { src: '8.jpg',      category: 'Outdoors' },
  { src: '9.jpg',      category: 'Outdoors' },
  { src: '10.jpg',     category: 'Outdoors' },
  { src: '11.jpg',     category: 'Outdoors' },
  { src: '12.jpg',     category: 'Outdoors' },
  { src: '14.jpg',     category: 'Outdoors' },
  { src: '15.jpg',     category: 'Outdoors' },
  { src: '16.jpg',     category: 'Outdoors' },
  { src: '17.jpg',     category: 'Outdoors' },
  { src: '18.jpg',     category: 'Outdoors' },
  { src: '20.jpg',     category: 'Grad' },
  { src: '21.jpg',     category: 'Grad' },
  { src: '22.jpg',     category: 'Grad' },
  { src: '23.jpg',     category: 'Grad' },
  { src: '24.jpg',     category: 'Grad' },
  { src: '25.jpg',     category: 'Grad' },
]

const categories = ['All', 'Family', 'Outdoors', 'Grad']

export default function Portfolio() {
  const [active, setActive] = useState('All')

  const filtered = active === 'All' ? images : images.filter(img => img.category === active)

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
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setActive(cat)}
              className={`font-sans text-xs font-medium tracking-widest uppercase px-6 py-2.5 transition-all duration-200 ${
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
          {filtered.map(({ src }) => (
            <div key={src} className="break-inside-avoid overflow-hidden group cursor-pointer">
              <img
                src={src}
                alt="Portrait"
                className="w-full object-cover transition-transform duration-700 group-hover:scale-105"
              />
            </div>
          ))}
        </div>

        <div className="text-center mt-12">
          <a href="#contact" className="btn-outline">
            Book Your Session
          </a>
        </div>
      </div>
    </section>
  )
}
