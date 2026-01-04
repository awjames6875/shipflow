'use client';

import { useState, useEffect } from 'react';
import {
  Play,
  CheckCircle,
  AlertCircle,
  Loader2,
  Sparkles,
  Wand2,
  Radio,
  Film,
  Send,
  ArrowRight,
  Clock,
  Zap,
} from 'lucide-react';

interface WorkflowResult {
  status: string;
  steps: Record<string, { status: string; preview?: string; video_url?: string; message?: string }>;
  error?: string;
}

interface Platform {
  id: string;
  name: string;
  icon: string;
  gradient: string;
  glowColor: string;
}

const PLATFORMS: Platform[] = [
  { id: 'tiktok', name: 'TikTok', icon: '♪', gradient: 'from-[#ff0050] to-[#00f2ea]', glowColor: 'rgba(255, 0, 80, 0.3)' },
  { id: 'instagram', name: 'Instagram', icon: '◎', gradient: 'from-[#f09433] via-[#dc2743] to-[#bc1888]', glowColor: 'rgba(220, 39, 67, 0.3)' },
  { id: 'youtube', name: 'YouTube', icon: '▶', gradient: 'from-[#ff0000] to-[#cc0000]', glowColor: 'rgba(255, 0, 0, 0.3)' },
  { id: 'facebook', name: 'Facebook', icon: 'f', gradient: 'from-[#1877f2] to-[#0d65d9]', glowColor: 'rgba(24, 119, 242, 0.3)' },
  { id: 'twitter', name: 'X', icon: '𝕏', gradient: 'from-[#1da1f2] to-[#0d8bd9]', glowColor: 'rgba(29, 161, 242, 0.3)' },
  { id: 'bluesky', name: 'Bluesky', icon: '☁', gradient: 'from-[#0085ff] to-[#00c6ff]', glowColor: 'rgba(0, 133, 255, 0.3)' },
  { id: 'linkedin', name: 'LinkedIn', icon: 'in', gradient: 'from-[#0077b5] to-[#00a0dc]', glowColor: 'rgba(0, 119, 181, 0.3)' },
  { id: 'threads', name: 'Threads', icon: '@', gradient: 'from-[#000000] to-[#333333]', glowColor: 'rgba(255, 255, 255, 0.15)' },
  { id: 'pinterest', name: 'Pinterest', icon: '📌', gradient: 'from-[#e60023] to-[#bd081c]', glowColor: 'rgba(230, 0, 35, 0.3)' },
];

const DURATION_OPTIONS = [
  { value: 15, label: '15s', description: 'Quick hook' },
  { value: 30, label: '30s', description: 'Standard' },
  { value: 45, label: '45s', description: 'Detailed' },
  { value: 60, label: '60s', description: 'In-depth' },
];

export default function Home() {
  const [industry, setIndustry] = useState('');
  const [scriptLength, setScriptLength] = useState(30);
  const [platforms, setPlatforms] = useState<string[]>(['tiktok', 'instagram', 'youtube']);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<WorkflowResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const togglePlatform = (id: string) => {
    setPlatforms((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!industry.trim() || platforms.length === 0) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setCurrentStep('Initializing workflow...');

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 25 * 60 * 1000);

    try {
      const response = await fetch('http://localhost:8000/workflow/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          industry,
          script_length_seconds: scriptLength,
          platforms,
        }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      clearTimeout(timeoutId);
      if (err instanceof Error && err.name === 'AbortError') {
        setError('Request timed out. Check backend logs for status.');
      } else {
        setError(err instanceof Error ? err.message : 'An unexpected error occurred');
      }
    } finally {
      setLoading(false);
      setCurrentStep(null);
    }
  };

  if (!mounted) return null;

  return (
    <main className="min-h-screen bg-[var(--color-void)] relative overflow-hidden">
      {/* Noise overlay */}
      <div className="noise-overlay" />

      {/* Ambient background effects */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-[var(--color-accent-amber)] opacity-[0.03] blur-[150px] rounded-full" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-[var(--color-accent-teal)] opacity-[0.03] blur-[150px] rounded-full" />
      </div>

      <div className="relative z-10">
        {/* Header */}
        <header className="border-b border-white/[0.04]">
          <div className="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[var(--color-accent-amber)] to-[var(--color-accent-rose)] flex items-center justify-center">
                <Zap className="w-4 h-4 text-white" />
              </div>
              <span className="font-display text-xl tracking-tight">ShipFlow</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-[var(--color-smoke)]">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Systems Online</span>
            </div>
          </div>
        </header>

        {/* Hero Section */}
        <section className="max-w-6xl mx-auto px-6 pt-20 pb-16">
          <div className="opacity-0 animate-fade-in-up" style={{ animationDelay: '100ms', animationFillMode: 'forwards' }}>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--color-charcoal)] border border-white/[0.06] text-xs text-[var(--color-mist)] mb-6">
              <Sparkles className="w-3 h-3 text-[var(--color-accent-amber)]" />
              AI-Powered Content Engine
            </div>
          </div>

          <h1
            className="font-display text-5xl md:text-7xl lg:text-8xl font-light tracking-tight mb-6 opacity-0 animate-fade-in-up"
            style={{ animationDelay: '200ms', animationFillMode: 'forwards' }}
          >
            <span className="gradient-text">Trending News</span>
            <br />
            <span className="text-[var(--color-mist)]">to Viral Videos</span>
          </h1>

          <p
            className="text-lg md:text-xl text-[var(--color-smoke)] max-w-xl leading-relaxed mb-12 opacity-0 animate-fade-in-up"
            style={{ animationDelay: '300ms', animationFillMode: 'forwards' }}
          >
            Transform any industry's breaking news into captivating AI avatar videos.
            Research, script, generate, and publish — all in one flow.
          </p>

          {/* Feature Pills */}
          <div
            className="flex flex-wrap gap-3 mb-16 opacity-0 animate-fade-in-up"
            style={{ animationDelay: '400ms', animationFillMode: 'forwards' }}
          >
            {[
              { icon: Radio, label: 'Perplexity Research' },
              { icon: Wand2, label: 'GPT-4o Scripts' },
              { icon: Film, label: 'HeyGen Avatar' },
              { icon: Send, label: '9 Platforms' },
            ].map((feature) => (
              <div
                key={feature.label}
                className="flex items-center gap-2 px-4 py-2 rounded-full glass-card-subtle text-sm text-[var(--color-mist)]"
              >
                <feature.icon className="w-4 h-4 text-[var(--color-accent-amber)]" />
                {feature.label}
              </div>
            ))}
          </div>
        </section>

        {/* Main Form Section */}
        <section className="max-w-4xl mx-auto px-6 pb-24">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Industry Input Card */}
            <div
              className="glass-card rounded-2xl p-8 opacity-0 animate-fade-in-up gradient-border"
              style={{ animationDelay: '500ms', animationFillMode: 'forwards' }}
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="w-8 h-8 rounded-lg bg-[var(--color-charcoal)] flex items-center justify-center">
                  <Radio className="w-4 h-4 text-[var(--color-accent-amber)]" />
                </div>
                <div>
                  <h3 className="font-medium text-[var(--color-cloud)]">Topic or Industry</h3>
                  <p className="text-xs text-[var(--color-smoke)]">What should we research?</p>
                </div>
              </div>
              <input
                type="text"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                placeholder="e.g., Real Estate, AI Technology, Cryptocurrency, Fitness..."
                className="w-full px-5 py-4 bg-[var(--color-charcoal)] border border-white/[0.04] rounded-xl text-[var(--color-cloud)] placeholder-[var(--color-smoke)] focus:border-[var(--color-accent-amber)]/30 focus:ring-1 focus:ring-[var(--color-accent-amber)]/20 transition-all text-lg"
              />
            </div>

            {/* Duration Selection Card */}
            <div
              className="glass-card rounded-2xl p-8 opacity-0 animate-fade-in-up gradient-border"
              style={{ animationDelay: '600ms', animationFillMode: 'forwards' }}
            >
              <div className="flex items-center gap-3 mb-6">
                <div className="w-8 h-8 rounded-lg bg-[var(--color-charcoal)] flex items-center justify-center">
                  <Clock className="w-4 h-4 text-[var(--color-accent-teal)]" />
                </div>
                <div>
                  <h3 className="font-medium text-[var(--color-cloud)]">Video Duration</h3>
                  <p className="text-xs text-[var(--color-smoke)]">Choose your content length</p>
                </div>
              </div>

              <div className="grid grid-cols-4 gap-3">
                {DURATION_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setScriptLength(option.value)}
                    className={`relative p-4 rounded-xl border transition-all ${
                      scriptLength === option.value
                        ? 'bg-gradient-to-br from-[var(--color-accent-amber)]/10 to-[var(--color-accent-rose)]/10 border-[var(--color-accent-amber)]/30'
                        : 'bg-[var(--color-charcoal)] border-white/[0.04] hover:border-white/[0.08]'
                    }`}
                  >
                    <div className={`text-2xl font-display mb-1 ${
                      scriptLength === option.value
                        ? 'gradient-text-accent'
                        : 'text-[var(--color-cloud)]'
                    }`}>
                      {option.label}
                    </div>
                    <div className="text-xs text-[var(--color-smoke)]">{option.description}</div>
                    {scriptLength === option.value && (
                      <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-[var(--color-accent-amber)]" />
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Platform Selection Card */}
            <div
              className="glass-card rounded-2xl p-8 opacity-0 animate-fade-in-up gradient-border"
              style={{ animationDelay: '700ms', animationFillMode: 'forwards' }}
            >
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-[var(--color-charcoal)] flex items-center justify-center">
                    <Send className="w-4 h-4 text-[var(--color-accent-rose)]" />
                  </div>
                  <div>
                    <h3 className="font-medium text-[var(--color-cloud)]">Distribution</h3>
                    <p className="text-xs text-[var(--color-smoke)]">Select target platforms</p>
                  </div>
                </div>
                <div className="text-sm text-[var(--color-smoke)]">
                  <span className="text-[var(--color-accent-amber)] font-medium">{platforms.length}</span> selected
                </div>
              </div>

              <div className="grid grid-cols-3 md:grid-cols-5 gap-3">
                {PLATFORMS.map((platform) => {
                  const isSelected = platforms.includes(platform.id);
                  return (
                    <button
                      key={platform.id}
                      type="button"
                      onClick={() => togglePlatform(platform.id)}
                      className={`platform-chip p-3 rounded-xl border text-center transition-all ${
                        isSelected
                          ? `bg-gradient-to-br ${platform.gradient} border-transparent selected`
                          : 'bg-[var(--color-charcoal)] border-white/[0.04] hover:border-white/[0.08]'
                      }`}
                      style={isSelected ? { '--glow-color': platform.glowColor } as React.CSSProperties : undefined}
                    >
                      <div className={`text-lg mb-1 ${isSelected ? 'text-white' : 'text-[var(--color-mist)]'}`}>
                        {platform.icon}
                      </div>
                      <div className={`text-xs font-medium ${isSelected ? 'text-white' : 'text-[var(--color-smoke)]'}`}>
                        {platform.name}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading || !industry.trim() || platforms.length === 0}
              className="w-full py-5 px-8 bg-gradient-to-r from-[var(--color-accent-amber)] via-[var(--color-accent-rose)] to-[var(--color-accent-amber)] bg-[length:200%_auto] text-white font-medium rounded-xl transition-all transform hover:scale-[1.01] hover:shadow-lg hover:shadow-[var(--color-accent-amber)]/20 disabled:opacity-40 disabled:hover:scale-100 disabled:cursor-not-allowed btn-shine flex items-center justify-center gap-3"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>{currentStep || 'Generating your viral video...'}</span>
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  <span>Generate & Publish</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Error Display */}
          {error && (
            <div className="mt-8 p-6 glass-card rounded-2xl border-[var(--color-accent-rose)]/30 animate-fade-in">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-xl bg-[var(--color-accent-rose)]/10 flex items-center justify-center flex-shrink-0">
                  <AlertCircle className="w-5 h-5 text-[var(--color-accent-rose)]" />
                </div>
                <div>
                  <h3 className="font-medium text-[var(--color-accent-rose)] mb-1">Error Occurred</h3>
                  <p className="text-sm text-[var(--color-mist)]">{error}</p>
                </div>
              </div>
            </div>
          )}

          {/* Results Display */}
          {result && (
            <div className="mt-8 space-y-4 animate-fade-in">
              <div
                className={`p-6 glass-card rounded-2xl ${
                  result.status === 'completed'
                    ? 'border-emerald-500/30'
                    : result.status === 'failed'
                    ? 'border-[var(--color-accent-rose)]/30'
                    : 'border-[var(--color-accent-amber)]/30'
                }`}
              >
                <div className="flex items-center gap-4 mb-6">
                  <div
                    className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                      result.status === 'completed'
                        ? 'bg-emerald-500/10'
                        : result.status === 'failed'
                        ? 'bg-[var(--color-accent-rose)]/10'
                        : 'bg-[var(--color-accent-amber)]/10'
                    }`}
                  >
                    {result.status === 'completed' ? (
                      <CheckCircle className="w-6 h-6 text-emerald-500" />
                    ) : result.status === 'failed' ? (
                      <AlertCircle className="w-6 h-6 text-[var(--color-accent-rose)]" />
                    ) : (
                      <Loader2 className="w-6 h-6 text-[var(--color-accent-amber)] animate-spin" />
                    )}
                  </div>
                  <div>
                    <h3 className="font-display text-xl">
                      {result.status === 'completed'
                        ? 'Video Published!'
                        : result.status === 'failed'
                        ? 'Generation Failed'
                        : 'Processing...'}
                    </h3>
                    <p className="text-sm text-[var(--color-smoke)]">
                      {Object.keys(result.steps).length} steps completed
                    </p>
                  </div>
                </div>

                <div className="space-y-3">
                  {Object.entries(result.steps).map(([stepName, step]) => (
                    <div
                      key={stepName}
                      className="flex items-start gap-4 p-4 rounded-xl bg-[var(--color-charcoal)]/50 border border-white/[0.02]"
                    >
                      <div className="flex-shrink-0 mt-0.5">
                        {step.status === 'completed' ? (
                          <CheckCircle className="w-4 h-4 text-emerald-500" />
                        ) : step.status === 'manual_required' ? (
                          <AlertCircle className="w-4 h-4 text-[var(--color-accent-amber)]" />
                        ) : (
                          <Loader2 className="w-4 h-4 text-[var(--color-accent-teal)] animate-spin" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-[var(--color-cloud)]">
                          {stepName.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                        </p>
                        {step.preview && (
                          <p className="text-xs text-[var(--color-smoke)] mt-1 line-clamp-2">
                            {step.preview}
                          </p>
                        )}
                        {step.video_url && (
                          <a
                            href={step.video_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-[var(--color-accent-amber)] hover:text-[var(--color-accent-rose)] mt-2 transition-colors"
                          >
                            <Film className="w-3 h-3" />
                            View Video
                            <ArrowRight className="w-3 h-3" />
                          </a>
                        )}
                        {step.message && (
                          <p className="text-xs text-[var(--color-accent-amber)] mt-1">
                            {step.message}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Footer */}
        <footer className="border-t border-white/[0.04] py-8">
          <div className="max-w-6xl mx-auto px-6 flex items-center justify-between text-xs text-[var(--color-smoke)]">
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded-lg bg-gradient-to-br from-[var(--color-accent-amber)] to-[var(--color-accent-rose)] flex items-center justify-center">
                <Zap className="w-2.5 h-2.5 text-white" />
              </div>
              <span>ShipFlow</span>
            </div>
            <div className="flex items-center gap-4">
              <span>Python FastAPI</span>
              <span className="text-[var(--color-ash)]">•</span>
              <span>Next.js 14</span>
              <span className="text-[var(--color-ash)]">•</span>
              <span>Tailwind CSS</span>
            </div>
          </div>
        </footer>
      </div>
    </main>
  );
}
