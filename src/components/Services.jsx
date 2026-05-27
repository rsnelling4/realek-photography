const packages = [
  {
    name: 'Mini Session',
    price: '$150',
    duration: '30 min',
    features: [
      '1 location',
      '15 edited digital images',
      'Online gallery delivery',
      'Personal use license',
    ],
    highlight: false,
  },
  {
    name: 'Portrait Session',
    price: '$300',
    duration: '1 hour',
    features: [
      'Up to 2 locations',
      '35 edited digital images',
      'Online gallery delivery',
      'Personal use license',
      'One outfit change',
    ],
    highlight: true,
  },
  {
    name: 'Extended Session',
    price: '$500',
    duration: '2–3 hours',
    features: [
      'Multiple locations',
      '60+ edited digital images',
      'Online gallery delivery',
      'Full print license',
      'Multiple outfit changes',
      'Print credit included',
    ],
    highlight: false,
  },
]

export default function Services() {
  return (
    <section id="services" className="py-24 px-6 bg-cream">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-16">
          <p className="section-label">Services & Pricing</p>
          <h2 className="section-heading">
            Sessions for Every<br />
            <em>Story</em>
          </h2>
          <p className="mt-4 text-taupe font-sans font-light text-lg max-w-md mx-auto">
            All sessions include a pre-shoot consultation to make sure we capture
            exactly what you're looking for.
          </p>
        </div>

        {/* Cards */}
        <div className="grid md:grid-cols-3 gap-8">
          {packages.map((pkg) => (
            <div
              key={pkg.name}
              className={`relative flex flex-col p-8 transition-shadow duration-300 hover:shadow-xl ${
                pkg.highlight
                  ? 'bg-dark-brown text-cream'
                  : 'bg-parchment text-dark-brown'
              }`}
            >
              {pkg.highlight && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-terracotta text-cream text-xs font-sans font-medium tracking-widest uppercase px-4 py-1">
                  Most Popular
                </span>
              )}

              <p
                className={`font-sans font-medium tracking-[0.15em] uppercase text-xs mb-2 ${
                  pkg.highlight ? 'text-terracotta' : 'text-terracotta'
                }`}
              >
                {pkg.duration}
              </p>
              <h3 className="font-serif text-2xl mb-1">{pkg.name}</h3>
              <div className="font-serif text-5xl font-semibold my-6">
                {pkg.price}
              </div>

              <ul className="space-y-3 flex-1 mb-8">
                {pkg.features.map((f) => (
                  <li key={f} className="flex items-start gap-3 font-sans text-sm font-light">
                    <span className="text-terracotta mt-0.5">✦</span>
                    <span className={pkg.highlight ? 'text-cream/80' : 'text-dark-brown/70'}>
                      {f}
                    </span>
                  </li>
                ))}
              </ul>

              <a
                href="#contact"
                className={`text-center py-3 px-6 font-sans font-medium tracking-wider uppercase text-sm transition-all duration-300 ${
                  pkg.highlight
                    ? 'bg-terracotta text-cream hover:bg-terracotta-dark'
                    : 'border border-terracotta text-terracotta hover:bg-terracotta hover:text-cream'
                }`}
              >
                Book This Session
              </a>
            </div>
          ))}
        </div>

        <p className="text-center text-taupe font-sans text-sm mt-10">
          Need something custom? <a href="#contact" className="text-terracotta underline underline-offset-2">Let's talk.</a>
        </p>
      </div>
    </section>
  )
}
