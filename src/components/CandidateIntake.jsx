// File: src/components/CandidateIntake.jsx
import React, { useEffect, useState, useRef } from 'react';
import FeedbackCard from './FeedbackCard';

const POLL_INTERVAL_MS = 1500;
const BUSY_NOTICE_MS = 45000;

const stageLabels = {
  idle: 'Ready',
  accepted: 'Queued...',
  queued: 'Queued...',
  parsing: 'Parsing...',
  intake: 'Parsing...',
  auditing: 'Auditing...',
  audit: 'Auditing...',
  optimizing: 'Optimizing...',
  optimize: 'Optimizing...',
  complete: 'Complete',
  completed: 'Complete',
  failed: 'Failed',
};

const normalizeStage = (stage) => String(stage || 'accepted').toLowerCase();

const parseFeedbackPoints = (result) => {
  if (Array.isArray(result?.top_feedback_points)) {
    return result.top_feedback_points;
  }

  const feedback = result?.ats_details?.actionable_feedback || '';
  return String(feedback)
    .split('\n')
    .map((line) => line.trim().replace(/^[\s\-*]+/, '').replace(/^\u2022\s*/, ''))
    .filter(Boolean)
    .slice(0, 5);
};

export default function CandidateIntake() {
  const [activeTab, setActiveTab] = useState('upload');
  const [file, setFile] = useState(null);
  const [searchError, setSearchError] = useState(null);
  const [warningBanner, setWarningBanner] = useState(null);
  const [pipelineStatus, setPipelineStatus] = useState('idle');
  const [pipelineMessage, setPipelineMessage] = useState('');
  const [pipelinePct, setPipelinePct] = useState(0);
  const [sessionId, setSessionId] = useState(null);
  const [finalResult, setFinalResult] = useState(null);
  const [feedbackPoints, setFeedbackPoints] = useState([]);
  const [candidateId, setCandidateId] = useState('');
  const [jobId, setJobId] = useState('');
  const [isStarting, setIsStarting] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [showBusyNotice, setShowBusyNotice] = useState(false);

  const [atsScore, setAtsScore] = useState(null);
  const [actionableFeedback, setActionableFeedback] = useState('');
  const [penalties, setPenalties] = useState(null);
  const [improvementAdvice, setImprovementAdvice] = useState([]);

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [technicalSkills, setTechnicalSkills] = useState('');
  const [workExperience, setWorkExperience] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});

  const fileInputRef = useRef(null);
  const activeRequestRef = useRef(false);
  const isRunning = isStarting || isPolling;

  useEffect(() => {
    if (!sessionId || !isPolling) {
      return undefined;
    }

    let isCancelled = false;

    const applyStatus = (statusPayload) => {
      const backendStatus = normalizeStage(statusPayload.status || statusPayload.workflow_status);
      const executionStage = normalizeStage(statusPayload.execution_stage || statusPayload.stage || backendStatus);
      const nextPct = statusPayload.execution_pct ?? statusPayload.pct ?? 0;
      const nextMessage = statusPayload.execution_message || statusPayload.message || stageLabels[executionStage] || executionStage;

      setPipelineStatus(executionStage);
      setPipelinePct(Math.min(Math.max(Number(nextPct) || 0, 0), 100));
      setPipelineMessage(nextMessage);

      if (backendStatus === 'failed' || executionStage === 'failed') {
        setIsPolling(false);
        activeRequestRef.current = false;
        setShowBusyNotice(false);
        setSearchError(nextMessage || 'Pipeline failed.');
        return;
      }

      if (backendStatus === 'completed' || executionStage === 'complete' || executionStage === 'completed') {
        const result = statusPayload.final_payload || statusPayload.result || {};
        setFinalResult(result);
        setFeedbackPoints(parseFeedbackPoints(result));
        setAtsScore(result.final_ats_score ?? result.matching_score ?? null);
        setPenalties(result.ats_details?.penalties || null);
        setActionableFeedback(result.ats_details?.actionable_feedback || '');
        setImprovementAdvice(result.ats_details?.improvement_advice || []);
        setPipelineStatus('complete');
        setPipelinePct(100);
        setPipelineMessage('Complete');
        setIsPolling(false);
        activeRequestRef.current = false;
        setShowBusyNotice(false);
      }
    };

    const pollStatus = async () => {
      try {
        const response = await fetch(`/match/${sessionId}/status`);
        if (!response.ok) {
          throw new Error(await response.text());
        }
        if (!isCancelled) {
          applyStatus(await response.json());
        }
      } catch (error) {
        if (!isCancelled) {
          const parsedMsg = parseBackendError(error);
          setSearchError(parsedMsg);
          setPipelineStatus('failed');
          setPipelineMessage(parsedMsg);
          setIsPolling(false);
          activeRequestRef.current = false;
        }
      }
    };

    pollStatus();
    const intervalId = setInterval(pollStatus, POLL_INTERVAL_MS);
    const busyNoticeId = setTimeout(() => {
      if (!isCancelled) {
        setShowBusyNotice(true);
      }
    }, BUSY_NOTICE_MS);

    return () => {
      isCancelled = true;
      clearInterval(intervalId);
      clearTimeout(busyNoticeId);
    };
  }, [sessionId, isPolling]);

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
      // Keep the raw message when the backend returns plain text.
    }

    return cleanMessage;
  };

  const resetPipelineState = () => {
    setSearchError(null);
    setWarningBanner(null);
    setFinalResult(null);
    setFeedbackPoints([]);
    setAtsScore(null);
    setActionableFeedback('');
    setPenalties(null);
    setPipelineStatus('idle');
    setPipelineMessage('');
    setPipelinePct(0);
    setShowBusyNotice(false);
  };

  const validateForm = () => {
    const errors = {};

    if (activeTab === 'upload' && !file) {
      errors.file = true;
      setWarningBanner('Please upload a resume document before starting the pipeline.');
    }

    if (activeTab === 'scratch') {
      if (!fullName.trim()) errors.fullName = true;
      if (!email.trim()) errors.email = true;
      if (!technicalSkills.trim()) errors.technicalSkills = true;
      if (!workExperience.trim()) errors.workExperience = true;
      if (!candidateId.trim()) errors.candidateId = true;
    }

    if (!jobId.trim()) {
      errors.jobId = true;
      setWarningBanner('Please provide a target job id before starting the pipeline.');
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const buildStartRequest = () => {
    if (activeTab === 'upload') {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('job_id', jobId.trim());
      if (candidateId.trim()) formData.append('candidate_id', candidateId.trim());
      if (fullName.trim()) formData.append('full_name', fullName.trim());
      if (email.trim()) formData.append('email', email.trim());
      return { method: 'POST', body: formData };
    }

    return {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        candidate_id: Number(candidateId),
        job_id: Number(jobId),
      }),
    };
  };

  const startPipeline = async ({ force = false } = {}) => {
    if (!force && (activeRequestRef.current || isRunning)) {
      return;
    }

    resetPipelineState();
    if (!validateForm()) {
      return;
    }

    activeRequestRef.current = true;
    setIsStarting(true);
    setPipelineStatus('accepted');
    setPipelineMessage('Queued...');

    try {
      const response = await fetch('/pipeline/start', buildStartRequest());
      if (!response.ok) {
        throw new Error(await response.text());
      }

      const accepted = await response.json();
      setSessionId(accepted.session_id);
      setIsPolling(true);
    } catch (error) {
      const parsedMsg = parseBackendError(error);
      setPipelineStatus('failed');
      setPipelineMessage(parsedMsg);
      setSearchError(parsedMsg);
      activeRequestRef.current = false;
    } finally {
      setIsStarting(false);
    }
  };

  const handleOptimizationSubmit = async (event) => {
    event.preventDefault();
    await startPipeline();
  };

  const handleRetry = async () => {
    activeRequestRef.current = false;
    setIsPolling(false);
    setSessionId(null);
    await startPipeline({ force: true });
  };

  const finalScore = finalResult?.final_ats_score ?? finalResult?.matching_score;
  const downloadUrl = finalResult?.doc_url;

  return (
    <div className="relative p-6 max-w-lg mx-auto bg-slate-900 border border-slate-800 rounded-3xl shadow-xl">
      <div className="flex bg-slate-950 p-1.5 rounded-xl mb-6">
        <button
          type="button"
          disabled={isRunning}
          onClick={() => {
            setActiveTab('upload');
            setWarningBanner(null);
            setFieldErrors({});
          }}
          className={`flex-1 py-2 text-center text-sm font-semibold rounded-lg transition-all disabled:opacity-60 ${
            activeTab === 'upload' ? 'bg-emerald-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
          }`}
        >
          Upload Resume
        </button>
        <button
          type="button"
          disabled={isRunning}
          onClick={() => {
            setActiveTab('scratch');
            setWarningBanner(null);
            setFieldErrors({});
          }}
          className={`flex-1 py-2 text-center text-sm font-semibold rounded-lg transition-all disabled:opacity-60 ${
            activeTab === 'scratch' ? 'bg-emerald-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
          }`}
        >
          Build from Scratch
        </button>
      </div>

      {warningBanner && (
        <div className="p-4 bg-amber-950/40 border border-amber-500/50 rounded-xl text-amber-300 text-sm font-semibold mb-4">
          {warningBanner}
        </div>
      )}

      {showBusyNotice && isPolling && (
        <div className="p-4 bg-blue-950/40 border border-blue-500/50 rounded-xl text-blue-200 text-sm font-semibold mb-4">
          Service is busier than usual. Your optimization is still running.
        </div>
      )}

      <form onSubmit={handleOptimizationSubmit} className="space-y-4" noValidate>
        <div>
          <label className="block text-slate-300 text-xs font-bold uppercase tracking-wider mb-2">
            Full Name {activeTab === 'scratch' && <span className="text-red-400">*</span>}
          </label>
          <input
            type="text"
            value={fullName}
            disabled={isRunning}
            onChange={(e) => {
              setFullName(e.target.value);
              if (fieldErrors.fullName) setFieldErrors((prev) => ({ ...prev, fullName: false }));
            }}
            className={`w-full bg-slate-950 border ${
              fieldErrors.fullName ? 'border-red-500 focus:border-red-400' : 'border-slate-800 focus:border-emerald-500'
            } rounded-xl px-4 py-3 text-white focus:outline-none transition-colors disabled:opacity-60`}
            placeholder="John Doe"
          />
        </div>

        {activeTab === 'scratch' && (
          <div>
            <label className="block text-slate-300 text-xs font-bold uppercase tracking-wider mb-2">
              Email Address <span className="text-red-400">*</span>
            </label>
            <input
              type="email"
              value={email}
              disabled={isRunning}
              onChange={(e) => {
                setEmail(e.target.value);
                if (fieldErrors.email) setFieldErrors((prev) => ({ ...prev, email: false }));
              }}
              className={`w-full bg-slate-950 border ${
                fieldErrors.email ? 'border-red-500 focus:border-red-400' : 'border-slate-800 focus:border-emerald-500'
              } rounded-xl px-4 py-3 text-white focus:outline-none transition-colors disabled:opacity-60`}
              placeholder="john@example.com"
            />
          </div>
        )}

        {activeTab === 'upload' ? (
          <div>
            <label className="block text-slate-300 text-xs font-bold uppercase tracking-wider mb-2">
              Upload Resume File <span className="text-red-400">*</span>
            </label>
            <input
              ref={fileInputRef}
              type="file"
              disabled={isRunning}
              onChange={(e) => {
                setFile(e.target.files[0] || null);
                if (warningBanner) setWarningBanner(null);
                if (fieldErrors.file) setFieldErrors((prev) => ({ ...prev, file: false }));
              }}
              className={`w-full bg-slate-950 border ${
                fieldErrors.file ? 'border-red-500' : 'border-slate-800'
              } rounded-xl px-4 py-3 text-slate-400 focus:outline-none focus:border-emerald-500 transition-colors disabled:opacity-60 file:mr-4 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-emerald-950 file:text-emerald-400 hover:file:bg-emerald-900`}
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
                disabled={isRunning}
                onChange={(e) => {
                  setTechnicalSkills(e.target.value);
                  if (fieldErrors.technicalSkills) setFieldErrors((prev) => ({ ...prev, technicalSkills: false }));
                }}
                className={`w-full bg-slate-950 border ${
                  fieldErrors.technicalSkills ? 'border-red-500 focus:border-red-400' : 'border-slate-800 focus:border-emerald-500'
                } rounded-xl px-4 py-3 text-white focus:outline-none transition-colors disabled:opacity-60`}
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
                disabled={isRunning}
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
                } rounded-xl px-4 py-3 text-white focus:outline-none transition-colors min-h-[100px] resize-y disabled:opacity-60`}
                placeholder="Describe your work experience or key technical projects..."
              />
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-slate-300 text-xs font-bold uppercase tracking-wider mb-2">
              Candidate ID {activeTab === 'scratch' && <span className="text-red-400">*</span>}
            </label>
            <input
              type="number"
              min="1"
              value={candidateId}
              disabled={isRunning}
              onChange={(e) => {
                setCandidateId(e.target.value);
                if (fieldErrors.candidateId) setFieldErrors((prev) => ({ ...prev, candidateId: false }));
              }}
              className={`w-full bg-slate-950 border ${
                fieldErrors.candidateId ? 'border-red-500 focus:border-red-400' : 'border-slate-800 focus:border-emerald-500'
              } rounded-xl px-4 py-3 text-white focus:outline-none transition-colors disabled:opacity-60`}
              placeholder="Existing candidate"
            />
          </div>
          <div>
            <label className="block text-slate-300 text-xs font-bold uppercase tracking-wider mb-2">
              Job ID <span className="text-red-400">*</span>
            </label>
            <input
              type="number"
              min="1"
              value={jobId}
              disabled={isRunning}
              onChange={(e) => {
                setJobId(e.target.value);
                if (fieldErrors.jobId) setFieldErrors((prev) => ({ ...prev, jobId: false }));
              }}
              className={`w-full bg-slate-950 border ${
                fieldErrors.jobId ? 'border-red-500 focus:border-red-400' : 'border-slate-800 focus:border-emerald-500'
              } rounded-xl px-4 py-3 text-white focus:outline-none transition-colors disabled:opacity-60`}
              placeholder="Target job"
            />
          </div>
        </div>

        {pipelineStatus !== 'idle' && (
          <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl">
            <div className="flex items-center justify-between text-sm mb-3">
              <span className="font-semibold text-white">
                {pipelineMessage || stageLabels[pipelineStatus] || pipelineStatus}
              </span>
              <span className="text-slate-400">{pipelinePct}%</span>
            </div>
            <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-500 transition-all duration-500"
                style={{ width: `${pipelinePct}%` }}
              />
            </div>
            {sessionId && (
              <div className="mt-3 text-xs text-slate-500">Session: {sessionId}</div>
            )}
          </div>
        )}

        <FeedbackCard
          atsScore={atsScore}
          actionableFeedback={actionableFeedback}
          penalties={penalties}
          improvementAdvice={improvementAdvice}
        />

        {searchError && (
          <div className="p-4 bg-red-950/20 border border-red-800/30 rounded-xl text-red-300 text-sm">
            <div className="font-bold mb-3">Pipeline failed</div>
            <div>{searchError}</div>
            <button
              type="button"
              onClick={handleRetry}
              disabled={isRunning}
              className="mt-4 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-60 text-white font-bold rounded-lg transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {finalResult && (
          <div className="p-5 bg-emerald-950/20 border border-emerald-800/40 rounded-xl text-sm text-emerald-100 transition-opacity duration-500 opacity-100">
            <div className="flex items-center justify-between gap-4 mb-4">
              <div>
                <div className="text-xs uppercase tracking-wider text-emerald-300 font-bold">Final ATS Score</div>
                <div className="text-4xl font-black text-white mt-1">
                  {Math.round((Number(finalScore) || 0) * 100) / 100}
                </div>
              </div>
              <a
                href={downloadUrl || undefined}
                aria-disabled={!downloadUrl}
                className={`px-4 py-2 rounded-lg font-bold transition-colors ${
                  downloadUrl
                    ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                    : 'bg-slate-800 text-slate-500 pointer-events-none'
                }`}
              >
                Download Optimized Resume
              </a>
            </div>

            <div className="max-h-44 overflow-y-auto space-y-2 pr-1">
              {(feedbackPoints.length ? feedbackPoints : ['Resume optimized successfully.']).map((point, index) => (
                <div key={`${point}-${index}`} className="p-3 bg-slate-950/60 border border-emerald-900/30 rounded-lg">
                  {point}
                </div>
              ))}
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={isRunning}
          className="w-full py-4 bg-gradient-to-r from-emerald-500 via-teal-600 to-indigo-600 hover:from-emerald-400 hover:to-indigo-500 disabled:opacity-60 disabled:transform-none text-white font-bold rounded-xl transition-all shadow-lg shadow-emerald-500/25 hover:shadow-emerald-500/40 text-sm tracking-wider uppercase transform hover:-translate-y-0.5"
        >
          {isRunning ? stageLabels[pipelineStatus] || 'Running...' : 'Start Pipeline'}
        </button>
      </form>
    </div>
  );
}
