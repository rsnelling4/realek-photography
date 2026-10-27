const faqs = [
  {
    q: 'What kinds of sessions do you offer?',
    a: "Senior photos, family photos, engagement and couples sessions, milestones like first birthdays and maternity, or just-because photos. Planning a wedding? Reach out and let's talk about it.",
  },
  {
    q: 'Where do sessions take place?',
    a: "All sessions are outdoors — I don't have a studio. We'll pick a spot together that fits the look you want, whether that's an open field, a creek, the woods, or somewhere downtown.",
  },
  {
    q: 'When are you available?',
    a: 'I work full time, so sessions are scheduled on evenings and weekends. Evenings are great for that warm golden-hour light!',
  },
  {
    q: 'How many photos will I receive?',
    a: 'Mini Sessions include 15 edited digital images, Portrait Sessions include 30, and Extended Sessions include 60 or more.',
  },
  {
    q: "What if the packages are outside my budget?",
    a: "Please still reach out. My goal is to make photography possible for people who couldn't usually afford it, and I'm happy to work with what you can truly afford.",
  },
  {
    q: 'How do I book?',
    a: "Fill out the contact form below with the type of session and a date you have in mind. I'll get back to you within 24 hours.",
  },
]

export default function FAQ() {
  return (
    <section id="faq" className="py-24 px-6 bg-cream border-t border-dark-brown/10">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-12">
          <p className="section-label">Questions</p>
          <h2 className="section-heading">
            Good to<br />
            <em>Know</em>
          </h2>
        </div>

        <div className="divide-y divide-dark-brown/10 border-y border-dark-brown/10">
          {faqs.map(({ q, a }) => (
            <details key={q} className="group py-5">
              <summary className="flex items-center justify-between gap-6 cursor-pointer list-none font-serif text-xl text-dark-brown [&::-webkit-details-marker]:hidden">
                {q}
                <span className="text-terracotta text-2xl transition-transform duration-300 group-open:rotate-45">+</span>
              </summary>
              <p className="mt-3 pr-10 font-sans font-light text-dark-brown/70 leading-relaxed">{a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  )
}
