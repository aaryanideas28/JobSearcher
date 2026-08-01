// File: src/components/CandidateIntake.jsx
import React, { useState, useRef } from 'react';
import LowAtsInsufficientDataModal from './modals/LowAtsInsufficientDataModal';
import FeedbackCard from './FeedbackCard';

export default function CandidateIntake() {
  const [activeTab, setActiveTab] = useState('upload'); // 'upload' | 'scratch'
  const [file, setFile] = useState(null);
  const [searchError, setSearchError] = useState(null);
  const [warningBanner, setWarningBanner] = useState(null);
  
  // ATS Result & Feedback States
  const [atsScore, setAtsScore] = useState(null);
  const [actionableFeedback, setActionableFeedback] = useState('');
  const [penalties, setPenalties] = useState(null);
  
  // Scratch Form States
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [technicalSkills, setTechnicalSkills] = useState('');
  const [workExperience, setWorkExperience] = useState('');
  
  // Validation field errors for red highlighting
  const [fieldErrors, setFieldErrors] = useState({});

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
    setWarningBanner(null);
    setFieldErrors({});

    // 1. Check Upload Tab Validation
    if (activeTab === 'upload') {
      if (!file) {
        setWarningBanner('⚠️ Please upload a resume document before clicking Search/Generate.');
        return;
      }
    }

    // 2. Check Build from Scratch Tab Validation
    if (activeTab === 'scratch') {
      const errors = {};
      if (!fullName.trim()) errors.fullName = true;
      if (!email.trim()) errors.email = true;
      if (!technicalSkills.trim()) errors.technicalSkills = true;
      if (!workExperience.trim()) errors.workExperience = true;

      if (Object.keys(errors).length > 0) {
        setFieldErrors(errors);
        setWarningBanner('⚠️ Please complete the required resume fields before proceeding.');
        return;
      }
    }

    try {
      // API call execution after validation passes cleanly
      // const response = await api.optimizeResume(file, activeTab, { fullName, email, technicalSkills, workExperience });
    } catch (error) {
      const parsedMsg = parseBackendError(error);
      const lowerMsg = parsedMsg.toLowerCase();
      
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
    setShowLowAtsModal(false);
    
    setFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    setSearchError(null);
    setWarningBanner(null);
    setFieldErrors({});

    setActiveTab('scratch');

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
          type="button"
          onClick={() => {
            setActiveTab('upload');
            setWarningBanner(null);
            setFieldErrors({});
          }}
          className={`flex-1 py-2 text-center text-sm font-semibold rounded-lg transition-all ${
            activeTab === 'upload' ? 'bg-emerald-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
          }`}
        >
          Upload Resume
        </button>
        <button
          type="button"
          onClick={() => {
            setActiveTab('scratch');
            setWarningBanner(null);
            setFieldErrors({});
          }}
          className={`flex-1 py-2 text-center text-sm font-semibold rounded-lg transition-all ${
            activeTab === 'scratch' ? 'bg-emerald-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
          }`}
        >
          Build from Scratch
        </button>
      </div>

      {/* Warning Banner Alert */}
      {warningBanner && (
        <div className="p-4 bg-amber-950/40 border border-amber-500/50 rounded-xl text-amber-300 text-sm font-semibold mb-4">
          {warningBanner}
        </div>
      )}

      <form onSubmit={handleOptimizationSubmit} className="space-y-4" noValidate>
        {/* Full Name Input */}
        <div>
          <label className="block text-slate-300 text-xs font-bold uppercase tracking-wider mb-2">
            Full Name {activeTab === 'scratch' && <span className="text-red-400">*</span>}
          </label>
          <input
            ref={fullNameRef}
            type="text"
            value={fullName}
            onChange={(e) => {
              setFullName(e.target.value);
              if (fieldErrors.fullName) setFieldErrors((prev) => ({ ...prev, fullName: false }));
            }}
            className={`w-full bg-slate-950 border ${
              fieldErrors.fullName ? 'border-red-500 focus:border-red-400' : 'border-slate-800 focus:border-emerald-500'
            } rounded-xl px-4 py-3 text-white focus:outline-none transition-colors`}
            placeholder="John Doe"
          />
        </div>

        {/* Email Input for Scratch mode */}
        {activeTab === 'scratch' && (
          <div>
            <label className="block text-slate-300 text-xs font-bold uppercase tracking-wider mb-2">
              Email Address <span className="text-red-400">*</span>
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (fieldErrors.email) setFieldErrors((prev) => ({ ...prev, email: false }));
              }}
              className={`w-full bg-slate-950 border ${
                fieldErrors.email ? 'border-red-500 focus:border-red-400' : 'border-slate-800 focus:border-emerald-500'
              } rounded-xl px-4 py-3 text-white focus:outline-none transition-colors`}
              placeholder="john@example.com"
            />
          </div>
        )}

        {/* Tab Specific Content */}
        {activeTab === 'upload' ? (
          <div>
            <label className="block text-slate-300 text-xs font-bold uppercase tracking-wider mb-2">
              Upload Resume File <span className="text-red-400">*</span>
            </label>
            <input
              ref={fileInputRef}
              type="file"
              onChange={(e) => {
                setFile(e.target.files[0] || null);
                if (warningBanner) setWarningBanner(null);
              }}
              className={`w-full bg-slate-950 border ${
                fieldErrors.file ? 'border-red-500' : 'border-slate-800'
              } rounded-xl px-4 py-3 text-slate-400 focus:outline-none focus:border-emerald-500 transition-colors file:mr-4 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-emerald-950 file:text-emerald-400 hover:file:bg-emerald-900`}
            />
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="block text-slate-300 text-xs font-bold uppercase tracking-wider mb-2">
                Technical Skills <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={technicalSkills}
                onChange={(e) => {
                  setTechnicalSkills(e.target.value);
                  if (fieldErrors.technicalSkills) setFieldErrors((prev) => ({ ...prev, technicalSkills: false }));
                }}
                className={`w-full bg-slate-950 border ${
                  fieldErrors.technicalSkills ? 'border-red-500 focus:border-red-400' : 'border-slate-800 focus:border-emerald-500'
                } rounded-xl px-4 py-3 text-white focus:outline-none transition-colors`}
                placeholder="Python, FastAPI, React, SQL"
              />
            </div>

            <div>
              <label className="block text-slate-300 text-xs font-bold uppercase tracking-wider mb-2">
                Work Experience / Projects <span className="text-red-400">*</span>
              </label>
              <textarea
                rows={3}
                value={workExperience}
                onChange={(e) => {
                  setWorkExperience(e.target.value);
                  if (fieldErrors.workExperience) setFieldErrors((prev) => ({ ...prev, workExperience: false }));
                }}
                onInput={(e) => {
                  e.target.style.height = 'auto';
                  e.target.style.height = e.target.scrollHeight + 'px';
                }}
                className={`w-full bg-slate-950 border ${
                  fieldErrors.workExperience ? 'border-red-500 focus:border-red-400' : 'border-slate-800 focus:border-emerald-500'
                } rounded-xl px-4 py-3 text-white focus:outline-none transition-colors min-h-[100px] resize-y`}
                placeholder="Describe your work experience or key technical projects..."
              />
            </div>
          </div>
        )}

        {/* Dynamic Actionable Feedback Card for scores < 75% */}
        <FeedbackCard
          atsScore={atsScore}
          actionableFeedback={actionableFeedback}
          penalties={penalties}
        />

        {/* Search Error Message Box */}
        {searchError && !showLowAtsModal && (
          <div className="p-4 bg-red-950/20 border border-red-800/30 rounded-xl text-red-400 text-sm">
            <strong>Error:</strong> {searchError}
          </div>
        )}

        <button
          type="submit"
          className="w-full py-4 bg-gradient-to-r from-emerald-500 via-teal-600 to-indigo-600 hover:from-emerald-400 hover:to-indigo-500 text-white font-bold rounded-xl transition-all shadow-lg shadow-emerald-500/25 hover:shadow-emerald-500/40 text-sm tracking-wider uppercase transform hover:-translate-y-0.5"
        >
          🔍 Search Target Jobs
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
