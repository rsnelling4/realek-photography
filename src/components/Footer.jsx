export default function Footer() {
  const year = new Date().getFullYear()

  return (
    <footer className="bg-dark-brown text-cream/60 py-10 px-6">
      <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        <a href="#hero" className="font-serif text-lg font-semibold text-cream tracking-wide">
          REALEK<span className="text-terracotta">.</span>
        </a>
        <p className="font-sans text-xs text-center">
          © {year} REALEK Photography. All rights reserved.
        </p>
        <div className="flex gap-6 font-sans text-xs tracking-widest uppercase">
          <a href="#portfolio" className="hover:text-terracotta transition-colors">Portfolio</a>
          <a href="#services" className="hover:text-terracotta transition-colors">Services</a>
          <a href="#contact" className="hover:text-terracotta transition-colors">Contact</a>
        </div>
      </div>
    </footer>
  )
}
