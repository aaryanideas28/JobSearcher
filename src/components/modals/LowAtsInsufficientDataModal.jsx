// File: src/components/modals/LowAtsInsufficientDataModal.jsx
import React from 'react';

/**
 * Screen-centered modal overlay for warning user about a low ATS score resume with insufficient details,
 * forcing them to switch to building a resume from scratch.
 *
 * @param {Object} props
 * @param {boolean} props.isOpen - Dictates if the modal is shown
 * @param {string} props.errorMessage - The parsed clean backend error message
 * @param {Function} props.onSwitchToScratch - Action handler when switching to building from scratch
 */
export default function LowAtsInsufficientDataModal({
  isOpen,
  errorMessage,
  onSwitchToScratch,
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-[#0F172A] border border-red-500/30 rounded-2xl p-6 shadow-2xl text-center">
        {/* Animated warning icon badge */}
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-500/10 text-red-500 text-3xl mb-4 animate-bounce">
          ⚠️
        </div>

        {/* Title */}
        <h2 className="text-white font-bold text-2xl mb-3 font-sans">
          Low ATS Match & Insufficient Details
        </h2>

        {/* Description */}
        <p className="text-slate-300 text-sm leading-relaxed mb-6">
          {errorMessage || "The uploaded resume lacks sufficient experience and skills for safe AI optimization without making assumptions."}
        </p>

        {/* Action Button */}
        <button
          onClick={onSwitchToScratch}
          className="w-full py-3.5 bg-red-600 hover:bg-red-700 text-white font-bold rounded-xl shadow-lg transition-all duration-200 cursor-pointer"
          type="button"
        >
          ✍️ Switch to Build from Scratch
        </button>
      </div>
    </div>
  );
}
