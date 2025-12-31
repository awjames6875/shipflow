'use client';

import { useState } from 'react';
import { Sparkles, Play, CheckCircle, AlertCircle, Loader2, Zap, Video, Share2 } from 'lucide-react';

interface WorkflowResult {
  status: string;
  steps: Record<string, { status: string; preview?: string; video_url?: string; message?: string }>;
  error?: string;
}

export default function Home() {
  const [industry, setIndustry] = useState('real estate');
  const [scriptLength, setScriptLength] = useState(30);
  const [platforms, setPlatforms] = useState(['tiktok', 'instagram', 'youtube']);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<WorkflowResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<string | null>(null);

  const allPlatforms = [
    { id: 'tiktok', name: 'TikTok', color: 'bg-pink-500' },
    { id: 'instagram', name: 'Instagram', color: 'bg-gradient-to-r from-purple-500 to-pink-500' },
    { id: 'youtube', name: 'YouTube', color: 'bg-red-500' },
    { id: 'linkedin', name: 'LinkedIn', color: 'bg-blue-600' },
    { id: 'twitter', name: 'Twitter/X', color: 'bg-gray-800' },
    { id: 'facebook', name: 'Facebook', color: 'bg-blue-500' },
    { id: 'threads', name: 'Threads', color: 'bg-gray-900' },
    { id: 'bluesky', name: 'Bluesky', color: 'bg-sky-500' },
    { id: 'pinterest', name: 'Pinterest', color: 'bg-red-600' },
  ];

  const togglePlatform = (id: string) => {
    setPlatforms(prev =>
      prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setCurrentStep('Starting workflow...');

    // 25-minute timeout for long-running workflow (HeyGen can take 15+ min)
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
        setError('Request timed out after 25 minutes. Check backend logs for status.');
      } else {
        setError(err instanceof Error ? err.message : 'An error occurred');
      }
    } finally {
      setLoading(false);
      setCurrentStep(null);
    }
  };

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      {/* Hero Section */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-purple-900/20 via-gray-950 to-pink-900/20" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-purple-500/10 via-transparent to-transparent" />

        <div className="relative max-w-6xl mx-auto px-6 pt-20 pb-16">
          <div className="flex items-center gap-2 mb-6">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
              <Sparkles className="h-4 w-4" />
            </div>
            <span className="text-sm font-medium text-purple-400">ShipFlow App</span>
          </div>

          <h1 className="text-5xl md:text-6xl font-bold mb-6 bg-gradient-to-r from-white via-purple-200 to-pink-200 bg-clip-text text-transparent">
            Viral News to<br />AI Avatar Videos
          </h1>

          <p className="text-xl text-gray-400 max-w-2xl mb-8">
            Automatically research trending news, generate scripts, create AI avatar videos,
            and post to 9 social platforms - all with one click.
          </p>

          <div className="flex flex-wrap gap-4 text-sm text-gray-500">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-yellow-500" />
              <span>Perplexity AI Research</span>
            </div>
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-purple-500" />
              <span>OpenAI Script Writing</span>
            </div>
            <div className="flex items-center gap-2">
              <Video className="h-4 w-4 text-pink-500" />
              <span>HeyGen Avatar Videos</span>
            </div>
            <div className="flex items-center gap-2">
              <Share2 className="h-4 w-4 text-blue-500" />
              <span>Blotato Multi-Platform</span>
            </div>
          </div>
        </div>
      </section>

      {/* Main Form Section */}
      <section className="max-w-4xl mx-auto px-6 pb-20">
        <form onSubmit={handleSubmit} className="space-y-8">
          {/* Industry Input */}
          <div className="bg-gray-900/50 backdrop-blur-sm border border-gray-800 rounded-2xl p-6">
            <label className="block text-sm font-medium text-gray-300 mb-3">
              Industry / Niche
            </label>
            <input
              type="text"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              placeholder="e.g., real estate, crypto, AI, fitness..."
              className="w-full px-4 py-3 bg-gray-800/50 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
            />
            <p className="mt-2 text-sm text-gray-500">
              We'll research the top trending news in this industry
            </p>
          </div>

          {/* Script Length */}
          <div className="bg-gray-900/50 backdrop-blur-sm border border-gray-800 rounded-2xl p-6">
            <label className="block text-sm font-medium text-gray-300 mb-3">
              Video Length: {scriptLength} seconds
            </label>
            <input
              type="range"
              min="15"
              max="60"
              step="5"
              value={scriptLength}
              onChange={(e) => setScriptLength(Number(e.target.value))}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-purple-500"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-2">
              <span>15s</span>
              <span>30s</span>
              <span>45s</span>
              <span>60s</span>
            </div>
          </div>

          {/* Platform Selection */}
          <div className="bg-gray-900/50 backdrop-blur-sm border border-gray-800 rounded-2xl p-6">
            <label className="block text-sm font-medium text-gray-300 mb-4">
              Post to Platforms
            </label>
            <div className="grid grid-cols-3 md:grid-cols-5 gap-3">
              {allPlatforms.map((platform) => (
                <button
                  key={platform.id}
                  type="button"
                  onClick={() => togglePlatform(platform.id)}
                  className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                    platforms.includes(platform.id)
                      ? `${platform.color} text-white shadow-lg`
                      : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                  }`}
                >
                  {platform.name}
                </button>
              ))}
            </div>
            <p className="mt-3 text-sm text-gray-500">
              {platforms.length} platform{platforms.length !== 1 ? 's' : ''} selected
            </p>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading || !industry.trim()}
            className="w-full py-4 px-6 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 disabled:from-gray-700 disabled:to-gray-700 text-white font-semibold rounded-xl transition-all transform hover:scale-[1.02] disabled:hover:scale-100 disabled:cursor-not-allowed flex items-center justify-center gap-3"
          >
            {loading ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                {currentStep || 'Processing...'}
              </>
            ) : (
              <>
                <Play className="h-5 w-5" />
                Generate Video & Post
              </>
            )}
          </button>
        </form>

        {/* Error Display */}
        {error && (
          <div className="mt-8 p-6 bg-red-900/20 border border-red-800 rounded-2xl">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-red-400 mt-0.5" />
              <div>
                <h3 className="font-medium text-red-400">Error</h3>
                <p className="text-sm text-red-300 mt-1">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Results Display */}
        {result && (
          <div className="mt-8 space-y-4">
            <div className={`p-6 rounded-2xl border ${
              result.status === 'completed'
                ? 'bg-green-900/20 border-green-800'
                : result.status === 'failed'
                ? 'bg-red-900/20 border-red-800'
                : 'bg-yellow-900/20 border-yellow-800'
            }`}>
              <div className="flex items-center gap-3 mb-4">
                {result.status === 'completed' ? (
                  <CheckCircle className="h-6 w-6 text-green-400" />
                ) : result.status === 'failed' ? (
                  <AlertCircle className="h-6 w-6 text-red-400" />
                ) : (
                  <Loader2 className="h-6 w-6 text-yellow-400 animate-spin" />
                )}
                <h3 className="text-lg font-semibold">
                  Workflow {result.status === 'completed' ? 'Completed' : result.status === 'failed' ? 'Failed' : 'In Progress'}
                </h3>
              </div>

              {/* Steps */}
              <div className="space-y-3">
                {Object.entries(result.steps).map(([stepName, step]) => (
                  <div
                    key={stepName}
                    className="flex items-start gap-3 p-3 bg-gray-800/50 rounded-lg"
                  >
                    {step.status === 'completed' ? (
                      <CheckCircle className="h-4 w-4 text-green-400 mt-0.5" />
                    ) : step.status === 'manual_required' ? (
                      <AlertCircle className="h-4 w-4 text-yellow-400 mt-0.5" />
                    ) : (
                      <Loader2 className="h-4 w-4 text-blue-400 animate-spin mt-0.5" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-300">
                        {stepName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </p>
                      {step.preview && (
                        <p className="text-xs text-gray-500 mt-1 truncate">
                          {step.preview}...
                        </p>
                      )}
                      {step.video_url && (
                        <a
                          href={step.video_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-purple-400 hover:text-purple-300 mt-1 inline-block"
                        >
                          View Video
                        </a>
                      )}
                      {step.message && (
                        <p className="text-xs text-yellow-400 mt-1">
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
      <footer className="border-t border-gray-800 py-8">
        <div className="max-w-6xl mx-auto px-6 text-center text-sm text-gray-500">
          <p>Generated by ShipFlow from n8n workflow</p>
          <p className="mt-1">Python/FastAPI Backend + Next.js Frontend</p>
        </div>
      </footer>
    </main>
  );
}
