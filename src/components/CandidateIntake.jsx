// File: src/components/CandidateIntake.jsx
import React, { useState, useRef } from 'react';
import LowAtsInsufficientDataModal from './modals/LowAtsInsufficientDataModal';

export default function CandidateIntake() {
  const [activeTab, setActiveTab] = useState('upload'); // 'upload' | 'scratch'
  const [file, setFile] = useState(null);
  const [searchError, setSearchError] = useState(null);
  
  // Modal states
  const [showLowAtsModal, setShowLowAtsModal] = useState(false);
  const [modalErrorDetails, setModalErrorDetails] = useState('');
  
  // Form input refs
  const fullNameRef = useRef(null);
  const fileInputRef = useRef(null);

  /**
   * Safe parser for backend error payloads (extracts detail text/message)
   */
  const parseBackendError = (error) => {
    let rawMessage = error?.message || error || 'Unknown backend error';
    let cleanMessage = rawMessage;

    try {
      const parsed = JSON.parse(rawMessage);
      if (parsed && parsed.detail) {
        if (typeof parsed.detail === 'string') {
          cleanMessage = parsed.detail;
        } else if (typeof parsed.detail === 'object' && parsed.detail.message) {
          cleanMessage = parsed.detail.message;
        } else {
          cleanMessage = JSON.stringify(parsed.detail);
        }
      }
    } catch (e) {
      // Message is not a JSON string, retain raw text
    }

    if (cleanMessage.startsWith('{"detail":')) {
      try {
        const parsed = JSON.parse(cleanMessage);
        cleanMessage = parsed.detail || cleanMessage;
      } catch (e) {}
    }

    return cleanMessage;
  };

  /**
   * Submits candidate profile or triggers resume optimization
   */
  const handleOptimizationSubmit = async (e) => {
    e.preventDefault();
    setSearchError(null);

    try {
      // Mock API call simulation
      // const response = await api.optimizeResume(file, activeTab);
    } catch (error) {
      const parsedMsg = parseBackendError(error);
      const lowerMsg = parsedMsg.toLowerCase();
      
      // Determine if error indicates low ATS score & insufficient data
      const isLowAtsInsufficient = (lowerMsg.includes('ats') || lowerMsg.includes('insufficient')) &&
                                    (lowerMsg.includes('scratch') || lowerMsg.includes('below 80'));

      if (isLowAtsInsufficient) {
        setModalErrorDetails(parsedMsg);
        setShowLowAtsModal(true);
      }
      
      setSearchError(parsedMsg);
    }
  };

  /**
   * Action handler triggered when clicking "Switch to Build from Scratch" modal button
   */
  const handleSwitchToScratch = () => {
    // 1. Dismiss the modal
    setShowLowAtsModal(false);
    
    // 2. Clear file upload selection and reset search error state
    setFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    setSearchError(null);

    // 3. Programmatically switch the active intake tab state
    setActiveTab('scratch');

    // 4. Scroll smoothly or focus the first input of the structured form
    setTimeout(() => {
      if (fullNameRef.current) {
        fullNameRef.current.focus();
        fullNameRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 150);
  };

  return (
    <div className="relative p-6 max-w-lg mx-auto bg-slate-900 border border-slate-800 rounded-3xl shadow-xl">
      {/* Tab Selectors */}
      <div className="flex bg-slate-950 p-1.5 rounded-xl mb-6">
        <button
          onClick={() => setActiveTab('upload')}
          className={`flex-1 py-2 text-center text-sm font-semibold rounded-lg transition-all ${
            activeTab === 'upload' ? 'bg-emerald-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
          }`}
        >
          Upload Resume
        </button>
        <button
          onClick={() => setActiveTab('scratch')}
          className={`flex-1 py-2 text-center text-sm font-semibold rounded-lg transition-all ${
            activeTab === 'scratch' ? 'bg-emerald-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
          }`}
        >
          Build from Scratch
        </button>
      </div>

      <form onSubmit={handleOptimizationSubmit} className="space-y-4">
        {/* Full Name Input */}
        <div>
          <label className="block text-slate-300 text-xs font-bold uppercase tracking-wider mb-2">Full Name</label>
          <input
            ref={fullNameRef}
            type="text"
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500 transition-colors"
            placeholder="John Doe"
            required
          />
        </div>

        {/* Tab Specific Content */}
        {activeTab === 'upload' ? (
          <div>
            <label className="block text-slate-300 text-xs font-bold uppercase tracking-wider mb-2">Upload Resume File</label>
            <input
              ref={fileInputRef}
              type="file"
              onChange={(e) => setFile(e.target.files[0])}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-slate-400 focus:outline-none focus:border-emerald-500 transition-colors file:mr-4 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-emerald-950 file:text-emerald-400 hover:file:bg-emerald-900"
            />
          </div>
        ) : (
          <div className="bg-slate-950/50 p-4 border border-slate-800 rounded-xl text-center text-sm text-slate-400">
            📝 Fill out the sections below to compile a fresh resume.
          </div>
        )}

        {/* Search Error Message Box */}
        {searchError && !showLowAtsModal && (
          <div className="p-4 bg-red-950/20 border border-red-800/30 rounded-xl text-red-400 text-sm">
            <strong>Error:</strong> {searchError}
          </div>
        )}

        <button
          type="submit"
          className="w-full py-3.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-xl transition-all shadow-md"
        >
          Search Target Jobs
        </button>
      </form>

      {/* Screen-centered warning modal */}
      <LowAtsInsufficientDataModal
        isOpen={showLowAtsModal}
        errorMessage={modalErrorDetails}
        onSwitchToScratch={handleSwitchToScratch}
      />
    </div>
  );
}
