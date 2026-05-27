export default function Hero() {
  return (
    <section id="hero" className="relative min-h-screen flex items-center justify-center overflow-hidden">
      {/* Background placeholder image */}
      <div className="absolute inset-0 z-0">
        <img
          src="2.jpg"
          alt="Hero portrait"
          className="w-full h-full object-cover object-center"
        />
        <div className="absolute inset-0 bg-dark-brown/45" />
      </div>

      {/* Content */}
      <div className="relative z-10 text-center px-6 max-w-3xl mx-auto">
        <p className="text-cream/70 font-sans font-medium tracking-[0.3em] uppercase text-xs mb-6">
          REALEK Photography
        </p>
        <h1 className="font-serif text-5xl md:text-7xl text-cream leading-tight mb-6">
          Capture Every<br />
          <em>Authentic</em> Moment
        </h1>
        <p className="text-cream/80 font-sans font-light text-lg md:text-xl leading-relaxed mb-10 max-w-xl mx-auto">
          Warm, natural portraits that tell the story of who you are —
          genuine, timeless, and beautifully yours.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <a href="#portfolio" className="btn-primary">
            View My Work
          </a>
          <a href="#contact" className="btn-outline border-cream/60 text-cream hover:bg-cream hover:text-dark-brown">
            Book a Session
          </a>
        </div>
      </div>

      {/* Scroll indicator */}
      <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-2 text-cream/50">
        <span className="font-sans text-xs tracking-widest uppercase">Scroll</span>
        <div className="w-px h-12 bg-cream/30 animate-pulse" />
      </div>
    </section>
  )
}
