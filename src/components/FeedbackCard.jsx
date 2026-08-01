// File: src/components/FeedbackCard.jsx
import React from 'react';

/**
 * FeedbackCard component renders actionable ATS feedback and penalty breakdowns
 * dynamically when the candidate's ATS score is < 75%.
 */
export default function FeedbackCard({ atsScore, actionableFeedback, penalties }) {
  if (atsScore === null || atsScore === undefined || atsScore >= 75) {
    return null;
  }

  // Parse feedback lines into separate bullet recommendations
  const lines = actionableFeedback
    ? actionableFeedback.split('\n').filter((l) => l.trim().length > 0)
    : [];

  const impactPenalty = penalties?.impact_verbs || 0;
  const formattingPenalty = penalties?.formatting || 0;
  const brevityPenalty = penalties?.brevity || 0;
  const metricsPenalty = penalties?.metrics || 0;
  const totalPenalties = penalties?.total_penalties || (impactPenalty + formattingPenalty + brevityPenalty + metricsPenalty);

  return (
    <div className="mt-4 p-5 bg-purple-950/40 border border-purple-800/40 rounded-2xl shadow-xl backdrop-blur-md transition-all duration-300">
      {/* Header Badge */}
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-purple-800/30">
        <div className="flex items-center gap-2">
          <span className="flex h-3 w-3 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500"></span>
          </span>
          <h4 className="text-amber-400 text-xs font-bold uppercase tracking-wider">
            ⚠️ Actionable Feedback Required (Score {atsScore}%)
          </h4>
        </div>
        {totalPenalties > 0 && (
          <span className="text-[11px] font-semibold text-red-400 bg-red-950/60 px-2.5 py-1 rounded-full border border-red-800/40">
            -{totalPenalties} pts Total Deductions
          </span>
        )}
      </div>

      {/* Penalty Breakdown Badges */}
      <div className="flex flex-wrap gap-2 mb-3">
        {impactPenalty > 0 && (
          <span className="text-[11px] font-medium text-amber-300 bg-amber-950/40 px-2 py-0.5 rounded-lg border border-amber-800/30">
            Impact Verbs: -{impactPenalty} pts
          </span>
        )}
        {metricsPenalty > 0 && (
          <span className="text-[11px] font-medium text-purple-300 bg-purple-900/40 px-2 py-0.5 rounded-lg border border-purple-700/30">
            Quantified Metrics: -{metricsPenalty} pts
          </span>
        )}
        {brevityPenalty > 0 && (
          <span className="text-[11px] font-medium text-blue-300 bg-blue-950/40 px-2 py-0.5 rounded-lg border border-blue-800/30">
            Brevity / Word Count: -{brevityPenalty} pts
          </span>
        )}
        {formattingPenalty > 0 && (
          <span className="text-[11px] font-medium text-rose-300 bg-rose-950/40 px-2 py-0.5 rounded-lg border border-rose-800/30">
            Formatting: -{formattingPenalty} pts
          </span>
        )}
      </div>

      {/* Bullet Recommendations */}
      <div className="space-y-2 text-xs text-purple-200/90 leading-relaxed">
        {lines.length > 0 ? (
          lines.map((line, idx) => (
            <div key={idx} className="flex items-start gap-2 bg-slate-900/40 p-2.5 rounded-xl border border-purple-900/20">
              <span className="text-amber-400 font-bold shrink-0 mt-0.5">💡</span>
              <p className="flex-1">{line.replace(/^[\s•\-*]+/, '')}</p>
            </div>
          ))
        ) : (
          <p className="italic text-purple-300/70">
            Add quantified metrics, strong action verbs, and missing technical keywords to increase your ATS match score above 75%.
          </p>
        )}
      </div>
    </div>
  );
}
