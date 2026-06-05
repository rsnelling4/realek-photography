import { useState } from 'react'

export default function Contact() {
  const [form, setForm] = useState({
    name: '',
    email: '',
    phone: '',
    service: '',
    message: '',
  })
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState(false)

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(false)
    const res = await fetch('https://formspree.io/f/mpqnbqyb', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(form),
    })
    if (res.ok) {
      setSubmitted(true)
    } else {
      setError(true)
    }
  }

  const inputClass =
    'w-full bg-transparent border-b border-dark-brown/20 focus:border-terracotta outline-none py-3 font-sans text-sm text-dark-brown placeholder-taupe/60 transition-colors duration-200'

  return (
    <section id="contact" className="py-24 bg-parchment">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid md:grid-cols-2 gap-16 items-start">
          {/* Left column */}
          <div>
            <p className="section-label">Get In Touch</p>
            <h2 className="section-heading mb-6">
              Let's Create<br />
              <em>Something Beautiful</em>
            </h2>
            <p className="text-dark-brown/70 font-sans font-light leading-relaxed mb-10">
              Ready to book a session or just have questions? Fill out the form
              and I'll get back to you within 24 hours. I can't wait to hear
              your story.
            </p>

            <div className="space-y-6">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-terracotta/10 flex items-center justify-center flex-shrink-0">
                  <span className="text-terracotta text-lg">✉</span>
                </div>
                <div>
                  <p className="font-sans text-xs tracking-widest uppercase text-taupe mb-0.5">Email</p>
                  <p className="font-sans text-sm text-dark-brown">hello@realekphotography.com</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-terracotta/10 flex items-center justify-center flex-shrink-0">
                  <span className="text-terracotta text-lg">📍</span>
                </div>
                <div>
                  <p className="font-sans text-xs tracking-widest uppercase text-taupe mb-0.5">Location</p>
                  <p className="font-sans text-sm text-dark-brown">Available Everywhere</p>
                </div>
              </div>
            </div>
          </div>

          {/* Form */}
          <div>
            {submitted ? (
              <div className="bg-cream p-10 text-center">
                <div className="text-terracotta text-4xl mb-4">✦</div>
                <h3 className="font-serif text-2xl text-dark-brown mb-3">Message Sent!</h3>
                <p className="font-sans text-sm text-taupe">
                  Thank you for reaching out. I'll be in touch within 24 hours.
                </p>
              </div>
            ) : (
              <>
                {error && (
                  <p className="bg-red-50 border border-red-200 text-red-700 font-sans text-sm px-4 py-3 mb-4">
                    Something went wrong. Please try again or email directly.
                  </p>
                )}
                <form onSubmit={handleSubmit} className="space-y-8 bg-cream p-10">
                <div>
                  <label className="font-sans text-xs tracking-widest uppercase text-taupe block mb-2">
                    Full Name *
                  </label>
                  <input
                    type="text"
                    name="name"
                    required
                    value={form.name}
                    onChange={handleChange}
                    placeholder="Jane Smith"
                    className={inputClass}
                  />
                </div>
                <div className="grid grid-cols-2 gap-6">
                  <div>
                    <label className="font-sans text-xs tracking-widest uppercase text-taupe block mb-2">
                      Email *
                    </label>
                    <input
                      type="email"
                      name="email"
                      required
                      value={form.email}
                      onChange={handleChange}
                      placeholder="jane@email.com"
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className="font-sans text-xs tracking-widest uppercase text-taupe block mb-2">
                      Phone
                    </label>
                    <input
                      type="tel"
                      name="phone"
                      value={form.phone}
                      onChange={handleChange}
                      placeholder="(555) 000-0000"
                      className={inputClass}
                    />
                  </div>
                </div>
                <div>
                  <label className="font-sans text-xs tracking-widest uppercase text-taupe block mb-2">
                    Session Type
                  </label>
                  <select
                    name="service"
                    value={form.service}
                    onChange={handleChange}
                    className={`${inputClass} bg-cream`}
                  >
                    <option value="">Select a package...</option>
                    <option value="mini">Mini Session — $100</option>
                    <option value="portrait">Portrait Session — $200</option>
                    <option value="extended">Extended Session — $400</option>
                    <option value="custom">Custom / Not Sure Yet</option>
                  </select>
                </div>
                <div>
                  <label className="font-sans text-xs tracking-widest uppercase text-taupe block mb-2">
                    Message *
                  </label>
                  <textarea
                    name="message"
                    required
                    rows={4}
                    value={form.message}
                    onChange={handleChange}
                    placeholder="Tell me about what you have in mind..."
                    className={`${inputClass} resize-none`}
                  />
                </div>
                <button type="submit" className="btn-primary w-full text-center">
                  Send Message
                </button>
              </form>
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
