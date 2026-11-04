import { useEffect, useState } from 'react'

const API = import.meta.env.VITE_TESTIMONIALS_URL

export default function Testimonials() {
  const [items, setItems] = useState([])

  useEffect(() => {
    if (!API) return
    fetch(`${API}/testimonials`)
      .then((res) => (res.ok ? res.json() : { testimonials: [] }))
      .then((data) => setItems(data.testimonials))
      .catch(() => {}) // the section just stays hidden; nothing else on the page depends on it
  }, [])

  if (items.length === 0) return null

  return (
    <section id="testimonials" className="py-24 px-6 bg-parchment">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <p className="section-label">Kind Words</p>
          <h2 className="section-heading">
            What Clients<br />
            <em>Are Saying</em>
          </h2>
        </div>
        <div className="flex flex-wrap justify-center gap-8">
          {items.map(({ id, name, text }) => (
            <figure key={id} className="bg-cream p-8 w-full md:w-[calc(50%-1rem)] lg:w-[calc(33.333%-1.34rem)]">
              <div aria-hidden="true" className="font-serif text-5xl leading-none text-terracotta mb-2">“</div>
              <blockquote className="font-sans font-light text-dark-brown/80 leading-relaxed whitespace-pre-line break-words">
                {text}
              </blockquote>
              <figcaption className="mt-6 font-serif italic text-lg text-dark-brown break-words">{name}</figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  )
}
