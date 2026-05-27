const images = [
  { src: '1.jpg',  span: '' },
  { src: '2.jpg',  span: '' },
  { src: '3.jpg',  span: '' },
  { src: '4.jpg',  span: 'row-span-2' },
  { src: '5.jpg',  span: 'row-span-2' },
  { src: '6.jpg',  span: '' },
  { src: '7.jpg',  span: '' },
  { src: '8.jpg',  span: 'row-span-2' },
  { src: '9.jpg',  span: 'row-span-2' },
  { src: '10.jpg', span: 'row-span-2' },
  { src: '12.jpg', span: 'row-span-2' },
  { src: '13.jpg', span: 'row-span-2' },
]

export default function Portfolio() {
  return (
    <section id="portfolio" className="py-24 px-6 bg-cream">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-16">
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

        {/* Grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 grid-rows-[auto] gap-3 md:gap-4 auto-rows-[200px]">
          {images.map(({ src, span }) => (
            <div
              key={src}
              className={`overflow-hidden group cursor-pointer ${span}`}
            >
              <img
                src={src}
                alt="Portrait"
                className="w-full h-full object-cover object-center transition-transform duration-700 group-hover:scale-105"
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
