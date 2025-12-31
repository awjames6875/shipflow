# ShipFlow Handoff State

**Date:** December 31, 2025
**Last Session:** Full workflow run - HeyGen timeout again

---

## Current Status: PAUSED - HeyGen Still Slow

The workflow ran successfully through research and script writing, but HeyGen video generation timed out after 11+ minutes.

**Pending Video ID:** `5ea84d4378664d1da8969d6ba88b6f20`

---

## What Was Working On

### Full Workflow Run (Today)
Executed `/run-shipflow` with:
- Industry: real estate
- Platforms: TikTok, Instagram, YouTube, Facebook, Twitter, Bluesky

**Results:**
| Step | Status | Details |
|------|--------|---------|
| Research top 10 | Completed | Found trending news |
| Research report | Completed | Detailed story analysis |
| Write script | Completed | "San Diego's Surprising December Market" |
| Create video | TIMED OUT | HeyGen still processing after 11 min |

### Discussed Faster Alternatives
User asked about faster video generation services:

| Service | Speed | Quality |
|---------|-------|---------|
| HeyGen | 5-15 min | Best |
| Synthesia | 2-5 min | Good |
| D-ID | 1-3 min | Good (fastest) |
| Colossyan | 3-7 min | Good |

**Recommendation:** D-ID as drop-in replacement if HeyGen continues to be slow.

---

## Code Fixes Applied (All Sessions)

1. **Blotato API header** - Fixed from `Authorization: Bearer` to `blotato-api-key`
2. **Account ID format** - Fixed from `acc_25109` to `25109` (numeric only)
3. **YouTube fields** - Added `privacyStatus`, `shouldNotifySubscribers`, `containsSyntheticMedia`
4. **TikTok fields** - Added 7 required fields including `isAiGenerated`, `privacyLevel`
5. **HeyGen subtitles** - Added `preset_name: "default"`
6. **Created test_blotato_direct.py** - Bypass server for direct testing
7. **Zombie process killer** - PowerShell one-liner for port cleanup

---

## Platform Status (Blotato)

| Platform | Status | Notes |
|----------|--------|-------|
| TikTok | Working | Tested successfully |
| Instagram | Working | Posts successfully |
| YouTube | Working | Fixed required fields |
| Facebook | Working | Has pageId configured |
| Twitter | Working | Ready |
| Bluesky | Working | Ready |
| Pinterest | Needs boardId | Skip for now |

---

## Next Steps

1. **Check pending video status:**
   ```bash
   curl -H "X-Api-Key: YOUR_KEY" "https://api.heygen.com/v1/video_status.get?video_id=5ea84d4378664d1da8969d6ba88b6f20"
   ```

2. **If video completed** - Post manually:
   ```bash
   curl -X POST http://localhost:8000/debug/blotato/test-all
   ```

3. **Consider D-ID integration** - Faster 1-3 min rendering

---

## Quick Start Commands

**Kill zombie processes:**
```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
```

**Start backend:**
```powershell
cd C:\Projects\shipflow-app\backend
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

**Start frontend:**
```powershell
cd C:\Projects\shipflow-app\frontend
npm run dev
```

**Test Blotato directly:**
```bash
cd C:\Projects\shipflow-app\backend
python test_blotato_direct.py
```

---

## Project Location

**USE:** `C:\Projects\shipflow-app\`

**DO NOT USE:** `C:\Users\1alph\OneDrive\Desktop\adam-skills-factory-complete\shipflow-app\`

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/app.py` | Main API + workflow |
| `backend/test_blotato_direct.py` | Direct Blotato test |
| `backend/.env` | All API keys |
| `frontend/src/app/page.tsx` | Dashboard UI |
| `CLAUDE.md` | Project instructions |

---

## Platform Account IDs

| Platform | Account ID |
|----------|------------|
| TikTok | 25109 |
| Instagram | 26256 |
| YouTube | 23118 |
| Facebook | 16601 |
| Twitter | 10976 |
| Bluesky | 18847 |

---

## Summary

Workflow works end-to-end. HeyGen is the bottleneck (5-15 min render time, sometimes timing out). Consider D-ID for faster video generation (1-3 min).
