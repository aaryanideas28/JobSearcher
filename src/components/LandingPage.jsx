// File: src/components/LandingPage.jsx
import React from 'react';

/**
 * LandingPage component - Pre-intake entry landing page for Stratum
 * Deep Purple brand theme (#1a0b36 / #260f54), Resume Worded style social proof cards,
 * ATS Compliance Guide, and 'Get Started' CTA.
 */
export default function LandingPage({ onGetStarted }) {
  return (
    <div className="min-h-screen bg-[#1a0b36] text-white font-[Inter,sans-serif] selection:bg-purple-600 selection:text-white">
      {/* Background Decorative Radial Gradient */}
      <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-purple-900/30 via-[#1a0b36] to-[#100624] -z-10" />

      {/* Navigation Header */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-[#1a0b36]/80 border-b border-purple-800/30 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-600 to-emerald-500 flex items-center justify-center font-extrabold text-white text-lg shadow-lg shadow-purple-900/40">
            S
          </div>
          <span className="font-['Space_Grotesk'] text-xl font-bold tracking-tight bg-gradient-to-r from-white via-purple-200 to-purple-400 bg-clip-text text-transparent">
            Stratum
          </span>
        </div>
        <button
          onClick={onGetStarted}
          className="px-5 py-2.5 bg-gradient-to-r from-purple-600 to-emerald-600 hover:from-purple-500 hover:to-emerald-500 text-white text-xs font-bold uppercase tracking-wider rounded-xl transition-all shadow-md shadow-purple-900/40 transform hover:-translate-y-0.5"
        >
          Get Started
        </button>
      </header>

      {/* Hero Banner Section */}
      <section className="max-w-6xl mx-auto px-6 pt-16 pb-20 text-center">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-purple-900/40 border border-purple-700/40 text-purple-300 text-xs font-semibold uppercase tracking-wider mb-6">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          Penalty-Based ATS Scoring Engine v2.0
        </div>
        
        <h1 className="font-['Space_Grotesk'] text-4xl sm:text-6xl font-extrabold text-white tracking-tight leading-tight mb-6 max-w-4xl mx-auto">
          Beat the ATS. Land More <span className="bg-gradient-to-r from-purple-400 via-pink-300 to-emerald-400 bg-clip-text text-transparent">High-Paying</span> Tech Interviews.
        </h1>

        <p className="text-purple-200/80 text-base sm:text-lg max-w-2xl mx-auto mb-10 leading-relaxed">
          Stratum uses industry-standard penalty-based calibration to give you realistic ATS scores and actionable feedback - no false validation.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <button
            onClick={onGetStarted}
            className="w-full sm:w-auto px-8 py-4 bg-gradient-to-r from-purple-600 via-indigo-600 to-emerald-600 hover:from-purple-500 hover:to-emerald-500 text-white font-bold rounded-xl shadow-xl shadow-purple-900/50 text-sm tracking-wider uppercase transition-all transform hover:-translate-y-1"
          >
            🚀 Scan & Optimize Resume Now
          </button>
        </div>
      </section>

      {/* Social Proof Section (Resume Worded Style Cards) */}
      <section className="max-w-6xl mx-auto px-6 py-12 border-t border-purple-800/20">
        <div className="text-center mb-12">
          <h2 className="font-['Space_Grotesk'] text-2xl sm:text-3xl font-bold text-white mb-3">
            Real Candidate Transformations
          </h2>
          <p className="text-purple-300/70 text-sm max-w-xl mx-auto">
            See how penalty-based feedback helped software engineers fix impact gaps and double their callback rates.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Card 1 */}
          <div className="bg-[#260f54]/60 border border-purple-700/30 rounded-2xl p-6 backdrop-blur-md shadow-xl hover:border-purple-600/50 transition-all">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-bold text-white text-base">Alex Chen</h3>
                <p className="text-purple-300/70 text-xs">Senior Full-Stack Engineer</p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-red-400 font-semibold bg-red-950/60 px-2 py-0.5 rounded border border-red-800/40">42% Before</span>
                <span className="text-xs text-emerald-400 font-bold bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/40">89% After</span>
              </div>
            </div>
            <div className="bg-slate-950/80 p-4 rounded-xl border border-purple-900/40 mb-4 font-mono text-xs text-purple-200">
              <p className="text-red-400/90 mb-1">❌ "Assisted with backend APIs and helped write SQL queries."</p>
              <p className="text-emerald-400 font-semibold">✓ "Architected high-throughput FastAPI endpoints serving 10,000+ daily requests, improving SQL latency by 45%."</p>
            </div>
            <p className="text-xs text-purple-200/80 italic">
              "Stratum pointed out weak verbs and missing metrics that other scanners missed. I got 3 callbacks in my first week."
            </p>
          </div>

          {/* Card 2 */}
          <div className="bg-[#260f54]/60 border border-purple-700/30 rounded-2xl p-6 backdrop-blur-md shadow-xl hover:border-purple-600/50 transition-all">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-bold text-white text-base">Sarah Jenkins</h3>
                <p className="text-purple-300/70 text-xs">DevOps & Cloud Engineer</p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-red-400 font-semibold bg-red-950/60 px-2 py-0.5 rounded border border-red-800/40">38% Before</span>
                <span className="text-xs text-emerald-400 font-bold bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/40">92% After</span>
              </div>
            </div>
            <div className="bg-slate-950/80 p-4 rounded-xl border border-purple-900/40 mb-4 font-mono text-xs text-purple-200">
              <p className="text-red-400/90 mb-1">❌ "Worked on Docker containers and AWS deployment."</p>
              <p className="text-emerald-400 font-semibold">✓ "Automated multi-region Docker deployment on AWS EKS using Terraform, cutting deployment downtime by 70%."</p>
            </div>
            <p className="text-xs text-purple-200/80 italic">
              "The penalty breakdown showed me that my resume failed due to lack of metrics. The automated DOCX output was pristine."
            </p>
          </div>
        </div>
      </section>

      {/* Educational Section: ATS Compliance Guide */}
      <section className="max-w-6xl mx-auto px-6 py-16 border-t border-purple-800/20">
        <div className="text-center mb-12">
          <h2 className="font-['Space_Grotesk'] text-2xl sm:text-3xl font-bold text-white mb-3">
            ATS Compliance Guidelines
          </h2>
          <p className="text-purple-300/70 text-sm max-w-xl mx-auto">
            Essential formatting rules enforced by Stratum to guarantee 100% parser accuracy across Workday, Greenhouse, and Lever.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="bg-[#260f54]/40 border border-purple-700/20 p-5 rounded-2xl">
            <div className="text-2xl mb-2">📌</div>
            <h3 className="font-bold text-white text-sm mb-1">Standard Section Titles</h3>
            <p className="text-xs text-purple-200/70 leading-relaxed">
              Use standard headers (Experience, Education, Skills, Projects). Avoid non-standard titles like "Where I've Been".
            </p>
          </div>

          <div className="bg-[#260f54]/40 border border-purple-700/20 p-5 rounded-2xl">
            <div className="text-2xl mb-2">🔤</div>
            <h3 className="font-bold text-white text-sm mb-1">Standard ATS Fonts</h3>
            <p className="text-xs text-purple-200/70 leading-relaxed">
              Stick to web-safe typography (Times New Roman, Arial, Calibri, Inter). Non-standard fonts confuse parser engines.
            </p>
          </div>

          <div className="bg-[#260f54]/40 border border-purple-700/20 p-5 rounded-2xl">
            <div className="text-2xl mb-2">📄</div>
            <h3 className="font-bold text-white text-sm mb-1">Single-Column Layout</h3>
            <p className="text-xs text-purple-200/70 leading-relaxed">
              Multi-column layouts cause text overlap during parsing. Always stick to clean single-column hierarchy.
            </p>
          </div>

          <div className="bg-[#260f54]/40 border border-purple-700/20 p-5 rounded-2xl">
            <div className="text-2xl mb-2">🚫</div>
            <h3 className="font-bold text-white text-sm mb-1">No Tables or Columns</h3>
            <p className="text-xs text-purple-200/70 leading-relaxed">
              Table borders and grid cells mangle parser text streams. Stratum penalizes heavy table structures.
            </p>
          </div>

          <div className="bg-[#260f54]/40 border border-purple-700/20 p-5 rounded-2xl">
            <div className="text-2xl mb-2">🖼️</div>
            <h3 className="font-bold text-white text-sm mb-1">No Scanned Diagrams / Images</h3>
            <p className="text-xs text-purple-200/70 leading-relaxed">
              ATS bots cannot read images, icons, or progress bars. Rely on clear text percentages and numbers.
            </p>
          </div>

          <div className="bg-[#260f54]/40 border border-purple-700/20 p-5 rounded-2xl">
            <div className="text-2xl mb-2">🎯</div>
            <h3 className="font-bold text-white text-sm mb-1">Quantified Business Impact</h3>
            <p className="text-xs text-purple-200/70 leading-relaxed">
              Include numbers, percentages (30%), currency ($50k), or multipliers (2x) in at least 50% of your experience bullets.
            </p>
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <footer className="border-t border-purple-800/30 py-10 text-center bg-[#100624]">
        <p className="text-purple-300/60 text-xs mb-4">Stratum AI Resume Automation Platform - Production Ready</p>
        <button
          onClick={onGetStarted}
          className="px-6 py-3 bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs uppercase tracking-wider rounded-xl transition-all"
        >
          Get Started Now →
        </button>
      </footer>
    </div>
  );
}
