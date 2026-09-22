import { Ban, House, IdCard, Search, Siren } from "lucide-react";
import { motion } from "motion/react";
import type { ReactNode } from "react";

interface Tip {
  icon: ReactNode;
  title: string;
  body: ReactNode;
}

const TIPS: Tip[] = [
  {
    icon: <Ban size={22} />,
    title: "Never pay to get a job",
    body: "Real employers don't charge registration, training, laptop or \"refundable\" security fees.",
  },
  {
    icon: <Search size={22} />,
    title: "Verify independently",
    body: "Find the official careers page or phone number yourself. Don't use links or numbers from the message.",
  },
  {
    icon: <IdCard size={22} />,
    title: "Protect your identity",
    body: "Don't send Aadhaar, PAN, bank details or OTPs before signing a verified contract.",
  },
  {
    icon: <House size={22} />,
    title: "Renting?",
    body: "Never pay a token or deposit before seeing the property in person and checking who owns it.",
  },
  {
    icon: <Siren size={22} />,
    title: "Report it fast",
    body: (
      <>
        File at{" "}
        <a href="https://cybercrime.gov.in" target="_blank" rel="noopener noreferrer">
          cybercrime.gov.in<span className="visually-hidden"> (opens in a new tab)</span>
        </a>{" "}
        or call <a href="tel:1930">1930</a>. If you already paid, report within hours.
      </>
    ),
  },
];

/** "What to do next" tips that animate in as they scroll into view. */
export function Advice() {
  return (
    <section className="card" aria-labelledby="advice-heading">
      <h2 id="advice-heading" className="card-title">
        <Siren size={24} aria-hidden="true" /> What to do next
      </h2>
      <motion.ul
        className="advice-grid"
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, amount: 0.2 }}
        variants={{ show: { transition: { staggerChildren: 0.1 } } }}
      >
        {TIPS.map((tip) => (
          <motion.li
            key={tip.title}
            className="advice-item"
            variants={{
              hidden: { opacity: 0, y: 30, rotateX: 25 },
              show: { opacity: 1, y: 0, rotateX: 0, transition: { type: "spring", stiffness: 140, damping: 18 } },
            }}
            whileHover={{ y: -6, scale: 1.02 }}
          >
            <motion.span
              className="advice-icon"
              aria-hidden="true"
              whileHover={{ rotate: [0, -12, 12, 0] }}
              transition={{ duration: 0.5 }}
            >
              {tip.icon}
            </motion.span>
            <h3>{tip.title}</h3>
            <p>{tip.body}</p>
          </motion.li>
        ))}
      </motion.ul>
    </section>
  );
}
