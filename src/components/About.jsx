export default function About() {
  return (
    <section id="about" className="py-24 bg-parchment">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid md:grid-cols-2 gap-16 items-center">
          {/* Image */}
          <div className="relative">
            <div className="aspect-[3/4] overflow-hidden">
              <img
                src="public/me.jpg"
                alt="Photographer"
                className="w-full h-full object-cover"
              />
            </div>
            {/* Decorative offset border */}
            <div className="absolute -bottom-4 -right-4 w-full h-full border-2 border-terracotta/30 -z-10" />
          </div>

          {/* Content */}
          <div>
            <p className="section-label">About Me</p>
            <h2 className="section-heading mb-6">
              Hello, I'm Ashley<br />
              <em>Your Photographer</em>
            </h2>
            <div className="space-y-4 text-dark-brown/70 font-sans font-light leading-relaxed text-base">
              <p>
              I wanted to offer my photography services to those who may not typically be able to afford it. 
              I am still learning but have the equipment, the software, the heart and the talent to produce some great images!
              </p>
              <p>
              I do have a family and value my time like the rest of us so I would like to be compensated, but only with what you can truly afford! 
              Times are tough and memories deserve to be captured and remembered for a lifetime and I'd love to help those who wouldn't be able to afford a professional! 
              </p>
              <p>
              I do not have a studio so these would be outdoor photos, I can do senior photos, family photos, engagement, milestone or just because photos. 
              I work full time so I would only be available in the evenings and on weekends.
              </p>
            </div>

          

            <div className="mt-10">
              <a href="#contact" className="btn-primary">
                Let's Connect
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
