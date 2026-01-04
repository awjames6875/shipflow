# n8n MASTER GOTCHAS - Complete Knowledge Base

> **Compiled from**: n8n Docs, Community Forum, GitHub Issues, and Real-World Experience
> **Last Updated**: December 2025
> **Total Gotchas**: 50+

---

## How This File Works

1. The Preflight Agent reads this file before validating any workflow
2. Each gotcha has detection rules so the agent can spot issues automatically
3. When YOU find a new issue, the agent asks permission to add it here
4. Over time, this becomes YOUR personal n8n expert knowledge base

---

# CRITICAL: Platform Differences (Cloud vs Self-Hosted)

## 1. Environment Variables Don't Work in n8n Cloud
**Problem:** `$env.X` references fail silently in n8n Cloud
**Error:** Workflow runs but API calls fail with auth errors, or expressions return undefined
**Detection:** Search JSON for `$env.` or `{{ $env`
**Fix:** Use n8n credentials system OR hardcode values for cloud deployment
**Auto-Fix Rule:** Flag all `$env.` references → Prompt user to replace with credentials

```javascript
// ❌ WRONG (works locally, breaks in cloud)
Authorization: Bearer {{$env.OPENAI_API_KEY}}

// ✅ CORRECT (for cloud)
// Use n8n's built-in credential system instead
```

---

## 2. Execution Timeout Limits (Cloud Only)
**Problem:** n8n Cloud has execution time limits that kill long-running workflows
**Error:** "Execution cancelled" or workflow just stops mid-run
**Detection:** Workflows with many HTTP requests, loops, or AI processing
**Fix:**
- Cloud Starter: ~10-20 minute limit
- If workflow needs >10 minutes, use self-hosted
- Split into multiple smaller workflows with webhooks between them
**Auto-Fix Rule:** Count nodes and estimate runtime → Warn if likely to exceed limits

---

## 3. WEBHOOK_URL Not Configured (Self-Hosted)
**Problem:** Webhooks generate wrong URLs like `localhost:5678` or include port numbers
**Error:** External services can't reach your webhook
**Detection:** Check if workflow has Webhook nodes + is for self-hosted
**Fix:** Set `WEBHOOK_URL=https://your-domain.com` in environment variables

```yaml
# docker-compose.yml
environment:
  - WEBHOOK_URL=https://n8n.yourdomain.com  # CRITICAL!
```

**Auto-Fix Rule:** Flag Webhook nodes → Remind user to verify WEBHOOK_URL is set

---

## 4. N8N_ENCRYPTION_KEY Not Set (Self-Hosted)
**Problem:** Credentials can't be decrypted after container restart or migration
**Error:** "Credentials could not be decrypted"
**Detection:** Self-hosted deployment
**Fix:** Set `N8N_ENCRYPTION_KEY` environment variable and NEVER change it
**Auto-Fix Rule:** Warn about credential encryption for self-hosted deployments

---

# EXPRESSION & SYNTAX ERRORS

## 5. Old Node Reference Syntax
**Problem:** `$('Node Name')` without `.first()` or `.all()` returns undefined
**Error:** "Cannot read property 'json' of undefined"
**Detection:** Regex for `\$\(['"][^'"]+['"]\)` without `.first()` or `.all()` following
**Fix:** Add `.first()` for single item or `.all()` for array

```javascript
// ❌ WRONG (old syntax, often breaks)
{{ $('HTTP Request').item.json.data }}

// ✅ CORRECT
{{ $json.data }}  // Current node's data

// ✅ CORRECT (explicit reference)
{{ $('HTTP Request').first().json.data }}  // First item
{{ $('HTTP Request').all() }}  // All items as array
```

**Auto-Fix Rule:** Detect `$('Node').item` → Replace with `$('Node').first()`

---

## 6. Expressions Inside URL Fields Break
**Problem:** Putting `{{ }}` expressions directly in URL fields causes parsing issues
**Error:** "Invalid URL" or mangled/malformed requests
**Detection:** URL fields containing `{{ }}` expressions
**Fix:** Use Query Parameters instead, or build URL in Code node first

```javascript
// ❌ WRONG (expression in URL)
https://api.example.com/users/{{ $json.userId }}/posts

// ✅ CORRECT (use Query Parameters)
URL: https://api.example.com/users
Query Params:
  - userId: {{ $json.userId }}

// ✅ CORRECT (build in Code node)
const url = `https://api.example.com/users/${$json.userId}/posts`;
return [{ json: { url } }];
```

**Auto-Fix Rule:** Detect `{{ }}` in URL strings → Flag for Query Parameter conversion

---

## 7. $json is Undefined
**Problem:** Expression can't find data because previous node hasn't run
**Error:** "Cannot read property of undefined" or just `[undefined]`
**Detection:** Expressions using `$json` or `$('Node')`
**Fix:**
- Ensure all previous nodes have executed
- Check if data structure matches what you're accessing
- Use optional chaining: `$json?.field?.nested`

```javascript
// ❌ WRONG (no null check)
{{ $json.data.items[0].name }}

// ✅ CORRECT (with null check)
{{ $json?.data?.items?.[0]?.name ?? 'default' }}
```

**Auto-Fix Rule:** Warn about deep property access without null checks

---

## 8. Referenced Node is Unexecuted
**Problem:** Expression references a node that hasn't run in current execution path
**Error:** "An expression references the node 'X', but it hasn't been executed yet"
**Detection:** Expressions referencing nodes that may not be in execution path
**Fix:** Ensure the referenced node is in the execution flow, or use IF node to handle both paths

---

## 9. Invalid JSON in Body/Parameters
**Problem:** JSON has syntax errors (missing quotes, extra commas, etc.)
**Error:** "The 'JSON Output' does not contain a valid JSON object"
**Detection:** JSON body fields with potential syntax issues
**Fix:** Validate JSON with a linter, check for:
- Missing quotes around keys
- Trailing commas
- Unescaped special characters

---

# HTTP REQUEST NODE ISSUES

## 10. Wrong HTTP Method
**Problem:** Using GET when API expects POST, or vice versa
**Error:** 404 Not Found, 405 Method Not Allowed
**Detection:** HTTP Request nodes
**Fix:** Check API documentation for correct method
**Auto-Fix Rule:** Flag HTTP nodes → Remind to verify method matches API docs

---

## 11. Missing or Wrong Content-Type Header
**Problem:** Content-Type doesn't match body format
**Error:** 400 Bad Request, 415 Unsupported Media Type
**Detection:** HTTP Request with body but wrong/missing Content-Type
**Fix:** Match Content-Type to your body:
- JSON body → `application/json`
- Form data → `application/x-www-form-urlencoded`
- File upload → `multipart/form-data`

```javascript
// ❌ WRONG
Content-Type: application/x-www-form-urlencoded
Body: { "name": "test" }  // This is JSON!

// ✅ CORRECT
Content-Type: application/json
Body: { "name": "test" }
```

**Auto-Fix Rule:** Detect JSON body with wrong Content-Type → Fix header

---

## 12. Authentication Header Issues
**Problem:** Auth header not being sent, or sent incorrectly
**Error:** 401 Unauthorized, 403 Forbidden
**Detection:** HTTP Request with authentication configured
**Known Bug:** Bearer auth sometimes doesn't pass through with pagination enabled
**Fix:**
- Try hardcoding Authorization header instead of using credentials
- Check if header name has correct capitalization
- Verify token format: `Bearer <token>` (with space)

```javascript
// ✅ Manual header (workaround for auth bugs)
Headers:
  Authorization: Bearer sk-xxxxx
```

**Auto-Fix Rule:** Flag auth-configured HTTP nodes → Suggest manual header as backup

---

## 13. Rate Limiting (429 Errors)
**Problem:** Too many requests to external API
**Error:** 429 Too Many Requests
**Detection:** HTTP Request nodes, especially in loops
**Fix:**
- Enable "Retry on Fail" in node options
- Add Wait node between requests
- Use Loop Over Items with batch size
- Set "Batching" option in HTTP Request node

**Auto-Fix Rule:** Detect HTTP nodes in loops → Suggest adding delays

---

## 14. SSL Certificate Issues
**Problem:** Self-signed or invalid SSL certificates block requests
**Error:** "UNABLE_TO_VERIFY_LEAF_SIGNATURE" or SSL errors
**Detection:** HTTP Request to internal/development servers
**Fix:** Enable "Ignore SSL Issues" option (use cautiously!)
**Auto-Fix Rule:** Flag SSL errors → Suggest Ignore SSL option for dev environments

---

# API-SPECIFIC GOTCHAS

## 15. Supabase: Missing Authorization Header
**Problem:** Supabase needs BOTH `apikey` AND `Authorization` headers
**Error:** 401 Unauthorized, "Invalid API key", Row Level Security violations
**Detection:** HTTP Request to `*.supabase.co` URLs
**Fix:** Include both headers:

```javascript
// ❌ WRONG (missing Authorization)
Headers:
  apikey: your-anon-key

// ✅ CORRECT (both required!)
Headers:
  apikey: your-anon-key
  Authorization: Bearer your-anon-key
  Content-Type: application/json
```

**Auto-Fix Rule:** Detect Supabase URL → Check for both headers → Add missing one

---

## 16. Supabase: Upsert Requires Special Header
**Problem:** Upsert operations fail without proper Prefer header
**Error:** Duplicate key errors or failed updates
**Detection:** POST to Supabase with upsert intent
**Fix:** Add `Prefer: resolution=merge-duplicates` header

**Auto-Fix Rule:** Detect Supabase upsert patterns → Add Prefer header

---

## 17. OpenAI: Deprecated Models
**Problem:** Old model names no longer work
**Error:** "Model not found" or "The model X has been deprecated"
**Detection:** OpenAI nodes or HTTP requests to OpenAI API
**Fix:** Update to current models:

| Old Model | Replace With |
|-----------|--------------|
| `text-davinci-003` | `gpt-4o` or `gpt-3.5-turbo` |
| `text-davinci-002` | `gpt-4o` |
| `code-davinci-002` | `gpt-4o` |
| `gpt-4-0314` | `gpt-4o` |
| `gpt-4-0613` | `gpt-4o` |
| `gpt-4-vision-preview` | `gpt-4o` |
| `gpt-3.5-turbo-0301` | `gpt-3.5-turbo` |

**Auto-Fix Rule:** Detect old model names → Replace with current version

---

## 18. OpenAI: Insufficient Quota
**Problem:** Account doesn't have credits or exceeded limits
**Error:** "Insufficient quota detected", 429 errors
**Detection:** OpenAI API errors
**Fix:**
- Check OpenAI billing page
- Verify correct organization/project selected
- Wait for quota refresh or add credits
- Issue new API key after adding credits (sometimes required)

---

## 19. OpenAI: Sub-Node Expression Limitation
**Problem:** OpenAI Chat Model (sub-node) always uses first item only
**Error:** Same response for all items in batch
**Detection:** OpenAI Chat Model connected to AI Agent with multiple input items
**Fix:** Use Loop Over Items to process one at a time, or use HTTP Request node instead

---

## 20. HeyGen: Async Video Generation
**Problem:** Video generation is async - immediate response doesn't contain video
**Error:** No error, but video URL is missing
**Detection:** HeyGen API calls
**Fix:** Implement polling loop:
1. Call create video → get video_id
2. Wait 5-10 seconds
3. Call status endpoint
4. If not complete, loop back to step 2
5. When complete, get video_url

**Auto-Fix Rule:** Detect HeyGen create video → Warn about async nature

---

## 21. HeyGen: Custom Avatar API Access (COMPLETE GUIDE)
**Problem:** Custom avatars created in HeyGen web app may not work via API - defaults to public avatar
**Error:** `400 Bad Request`, `avatar_not_found`, or video generates with wrong avatar
**Detection:** HeyGen API calls with custom avatar_id

### Root Causes (from Sabrina Ramonov video)

1. **Missing API Subscription (~$99/mo):** HeyGen requires a separate **API Plan** to use custom avatars. The "Creator" web plan is NOT enough for API access.
2. **Wrong ID Copied:** Dashboard shows "Group ID" and "Avatar ID" - you must click **"Copy Avatar ID"** specifically.
3. **Avatar Not Fully Processed:** Custom avatars must be 100% finished processing before API can use them.

### Step-by-Step Fix

**Step 1: Verify API Plan**
- Go to HeyGen Settings > Subscriptions
- Confirm you have an active **API Plan** (not just Creator/web plan)
- Without API plan, system defaults to public avatars only

**Step 2: Get Correct Avatar ID**
- Go to Avatar tab in HeyGen dashboard
- Hover over YOUR custom avatar
- Click **"Copy Avatar ID"** (NOT "Copy Group ID")
- ID should be 32 hex characters like `6749d17784bf4e2fa243e19965b786b0`

**Step 3: Verify Avatar is API-Accessible**
```bash
curl -X GET https://api.heygen.com/v2/avatars \
  -H "X-Api-Key: YOUR_API_KEY"
```
If your custom avatar is NOT in the response, it's not API-accessible (plan issue).

### Correct Payload Structure (from video)

The video recommends this structure with `clips` array:
```python
payload = {
    "video_setting": {
        "ratio": "9:16"
    },
    "clips": [{
        "avatar_id": "YOUR_CUSTOM_AVATAR_ID",  # At top level of clip
        "avatar_style": "normal",
        "input_text": "Your script here",
        "voice": {
            "voice_id": "YOUR_VOICE_ID"
        }
    }]
}
```

### Common Mistakes

| Mistake | Why It Fails | Fix |
|---------|--------------|-----|
| Only Creator plan | API needs separate subscription | Upgrade to API plan (~$99/mo) |
| Copied Group ID | Different from Avatar ID | Click "Copy Avatar ID" specifically |
| Avatar still processing | Must be 100% complete | Wait for processing to finish |
| Using V1 template endpoint | Forces public templates | Use V2 generate endpoint |

### Testing Checklist
- [ ] API Plan subscription is active (check Settings > Subscriptions)
- [ ] Avatar ID is from "Copy Avatar ID" button (not Group ID)
- [ ] Avatar appears in `GET /v2/avatars` response
- [ ] Avatar processing is 100% complete
- [ ] Test with public avatar first (e.g., `Anna_public_3_20240108`) to verify workflow works

### Additional Settings (from video)
- **Background removal:** Set `"matting": true` in character config
- **Wait time:** Allow 5-8 minutes for video generation before polling

**Auto-Fix Rule:** Detect HeyGen avatar_id → Warn about API plan requirement → Suggest testing with public avatar first

**Reference:** [Sabrina Ramonov HeyGen Tutorial](https://www.youtube.com/watch?v=0T3FjaxDISI)

---

# WEBHOOK ISSUES

## 22. Test URL vs Production URL
**Problem:** Using test URL in production, or vice versa
**Error:** Webhook doesn't trigger, or "Workflow not active"
**Detection:** Webhook nodes
**Fix:**
- Test URL: Only works when workflow is open and "Listening"
- Production URL: Only works when workflow is ACTIVE (toggle on)

**Auto-Fix Rule:** Remind user about URL differences

---

## 23. Webhook Path Conflicts
**Problem:** Two workflows using same webhook path
**Error:** "The path and method are already registered"
**Detection:** Duplicate webhook paths across workflows
**Fix:** Use unique paths for each webhook

---

## 24. Webhook 100-Second Timeout (Cloud)
**Problem:** n8n Cloud uses Cloudflare which times out at 100 seconds
**Error:** 524 status code
**Detection:** Webhook-triggered workflows with long processing
**Fix:**
- Send immediate response
- Process async
- Use second webhook to return results

---

## 25. Missing Respond to Webhook Node
**Problem:** Webhook returns default response instead of workflow output
**Error:** None (but caller gets wrong data)
**Detection:** Webhook node without Respond to Webhook at end
**Fix:** Add "Respond to Webhook" node at the end of workflow

```
✅ CORRECT PATTERN:
Webhook → Process → Process → Respond to Webhook
```

**Auto-Fix Rule:** Detect Webhook without Respond node → Warn

---

## 26. Webhook Not Publicly Accessible
**Problem:** External services can't reach webhook (firewall, localhost, etc.)
**Error:** Connection refused, timeout
**Detection:** Self-hosted deployment
**Fix:**
- Use ngrok for local testing
- Verify firewall rules
- Check WEBHOOK_URL environment variable

---

# LOOP & BATCH ISSUES

## 27. Loop Over Items: Batch Size Confusion
**Problem:** Not understanding how batch size affects processing
**Error:** Unexpected number of iterations or data
**Detection:** Loop Over Items nodes
**Fix:**
- Batch Size 1 = process one item at a time
- Batch Size 10 = process 10 items per iteration
- Use Batch Size 1 for nodes that only handle single items

---

## 28. Merge Node in Loops
**Problem:** Merge node doesn't work as expected inside loops
**Error:** Loop exits early, data missing
**Detection:** Merge node connected to Loop Over Items
**Fix:**
- Collect data AFTER loop completes (use "done" output)
- Don't connect Merge directly to loop's main output

---

## 29. Nested Loops Don't Reset
**Problem:** Inner loop doesn't reset index for each outer loop iteration
**Error:** Inner loop only runs once, or runs too many times
**Detection:** Split In Batches inside another Split In Batches
**Fix:** Enable "Reset" option on inner loop, or restructure workflow

---

## 30. Some Nodes Only Process First Item
**Problem:** Certain nodes only process first item in batch
**Error:** Missing data, incomplete results
**Detection:** These specific nodes in workflow:
- RSS Feed Read
- XML node
- Some trigger nodes
**Fix:** Wrap with Loop Over Items (batch size 1)

---

# CODE NODE ISSUES

## 31. Code Node Must Return Array of Objects
**Problem:** Returning wrong data structure
**Error:** "Code doesn't return items properly"
**Detection:** Code nodes
**Fix:** Always return array of objects with `json` property:

```javascript
// ❌ WRONG
return data;

// ❌ WRONG
return ['a', 'b', 'c'];

// ✅ CORRECT
return [{ json: { field: 'value' } }];

// ✅ CORRECT (multiple items)
return items.map(item => ({
  json: {
    ...item.json,
    newField: 'value'
  }
}));
```

**Auto-Fix Rule:** Check Code node return statements

---

## 32. $input.all() vs $json Confusion
**Problem:** Using wrong method for the execution mode
**Error:** Undefined or wrong data
**Detection:** Code nodes
**Fix:**
- "For Each Item" mode → use `$json` (single item)
- "Once for All Items" mode → use `$input.all()` (array)

```javascript
// For Each Item mode:
const name = $json.name;
return [{ json: { name } }];

// Once for All Items mode:
const allItems = $input.all();
const total = allItems.reduce((sum, item) => sum + item.json.amount, 0);
return [{ json: { total } }];
```

---

## 33. Async Code Without Await
**Problem:** Async operations complete after node finishes
**Error:** Empty results, undefined values
**Detection:** Code nodes with fetch, setTimeout, Promises
**Fix:** Use await and async function:

```javascript
// ❌ WRONG
fetch('https://api.example.com').then(r => r.json());

// ✅ CORRECT
const response = await fetch('https://api.example.com');
const data = await response.json();
return [{ json: data }];
```

---

## 34. Console.log Without Return
**Problem:** Using console.log for debugging but forgetting to return
**Error:** "Code doesn't return items properly"
**Detection:** Code nodes with only console.log
**Fix:** Always return something, even for debugging:

```javascript
console.log($json);
return [{ json: {} }];  // Must return something!
```

---

# CREDENTIAL & SECURITY ISSUES

## 35. Hardcoded API Keys in Workflow JSON
**Problem:** Sharing workflow exposes credentials
**Error:** None (security risk)
**Detection:** Patterns like `sk-`, `api_`, `key_`, `token_` in JSON values
**Fix:** Use n8n credentials system, never hardcode in workflow

**Auto-Fix Rule:** Detect credential patterns → Flag as security risk

---

## 36. Credentials Expire / Get Revoked
**Problem:** OAuth tokens expire, API keys get rotated
**Error:** 401 Unauthorized (workflow that used to work)
**Detection:** OAuth credentials, time-based tokens
**Fix:** Re-authenticate in n8n credentials, refresh tokens

---

## 37. Credential "No Access" After Editing
**Problem:** After editing a credential, nodes lose access to it
**Error:** "Node does not have access to the credential"
**Detection:** Known n8n bug
**Fix:** Create new credential instead of editing existing one

---

## 38. Docker Secrets Add Newline
**Problem:** Reading credentials from Docker secrets adds `\n` at end
**Error:** "Authentication failed for user 'username\n'"
**Detection:** Docker deployment with secrets
**Fix:** Trim the secret value or use environment variables instead

---

# WORKFLOW STRUCTURE ISSUES

## 39. No Trigger Node
**Problem:** Workflow doesn't have a trigger as first node
**Error:** "Workflow has issues and cannot be executed"
**Detection:** First node is not a trigger type
**Fix:** Add Manual Trigger, Webhook, Schedule, or other trigger as first node

**Auto-Fix Rule:** Detect workflows without trigger → Add Manual Trigger

---

## 40. Ghost/Orphan Nodes
**Problem:** Nodes exist but aren't connected to anything
**Error:** None (but confusing and may cause issues)
**Detection:** Nodes with 0 connections
**Fix:** Either connect them or delete them

**Auto-Fix Rule:** Detect disconnected nodes → Flag for removal

---

## 41. Missing Error Handling
**Problem:** Workflow fails silently with no notification
**Error:** None shown (but execution failed)
**Detection:** No Error Trigger workflow configured
**Fix:** Create Error Workflow with Error Trigger + notification (email, Slack)

**Auto-Fix Rule:** Check for error workflow → Suggest creating one

---

## 42. AI Agent Without Memory
**Problem:** AI Agent forgets context between messages
**Error:** None (but agent has no conversation context)
**Detection:** AI Agent node without connected memory node
**Fix:** Connect Window Buffer Memory or other memory node

```
✅ CORRECT:
Chat Trigger → AI Agent → Response
                  ↑
           Window Buffer Memory
```

**Auto-Fix Rule:** Detect AI Agent without memory → Suggest adding

---

# DATA HANDLING ISSUES

## 43. Data Mapping Mismatch Between Systems
**Problem:** Field names or types don't match between source and destination
**Error:** Missing data, wrong values, type errors
**Detection:** Merge nodes, data transformation
**Fix:** Use Edit Fields node to rename/transform fields

---

## 44. Array vs Object Confusion
**Problem:** Expecting object but getting array, or vice versa
**Error:** "Cannot read property X of undefined"
**Detection:** Data access expressions
**Fix:**
- Use `[0]` to get first item of array
- Use `.first()` for n8n item arrays
- Check actual data structure in output panel

---

## 45. Empty Array/No Items
**Problem:** Node receives empty input, subsequent nodes fail
**Error:** Various, or silent failure
**Detection:** Any workflow section
**Fix:** Add IF node to check for empty data:

```javascript
{{ $json.items?.length > 0 }}
```

---

## 46. Binary Data Handling
**Problem:** Files not properly passed between nodes
**Error:** Missing file, corrupted data
**Detection:** Nodes handling files (images, PDFs, etc.)
**Fix:**
- Enable "Binary Property" option
- Use correct binary property name (default: `data`)
- Check file size limits

---

# PERFORMANCE ISSUES

## 47. JavaScript Heap Out of Memory
**Problem:** Workflow uses too much memory
**Error:** "JavaScript heap out of memory"
**Detection:** Large data processing, many items, complex loops
**Fix:**
- Set `NODE_OPTIONS=--max-old-space-size=4096` (4GB)
- Split data into smaller batches
- Use streaming where possible

---

## 48. Workflow Timeout
**Problem:** Execution takes too long
**Error:** Timeout errors, cancelled execution
**Detection:** Many nodes, external API calls, complex processing
**Fix:**
- Optimize workflow (remove unnecessary nodes)
- Split into multiple workflows
- Use queue mode for long processes

---

## 49. Database Connection Pool Exhausted
**Problem:** Too many database connections
**Error:** "Database is not ready" or connection errors
**Detection:** Many database operations
**Fix:**
- Batch database operations
- Configure connection pool size
- Use transactions where appropriate

---

# VERSION/UPDATE ISSUES

## 50. Breaking Changes After Update
**Problem:** Workflow stops working after n8n update
**Error:** Various
**Detection:** Recent n8n update
**Fix:**
- Check n8n changelog for breaking changes
- Test in staging before updating production
- Keep backup of working workflows

Common breaking changes:
- Expression syntax changes (`$node` vs `$()`)
- Node version changes (typeVersion)
- Removed/renamed parameters

---

## 51. Node Type Version Mismatch
**Problem:** Workflow uses old node version
**Error:** Missing parameters, unexpected behavior
**Detection:** `typeVersion` in workflow JSON
**Fix:** Update node to latest version (may require reconfiguration)

---

## 52. HeyGen: Wrong Avatar ID (400 Bad Request)
**Problem:** Using group avatar ID instead of individual avatar ID
**Error:** `400 Bad Request` or `{"code":"invalid_parameter","message":"avatar_id is invalid"}`
**Detection:** HeyGen API calls with `avatar_id` parameter

### How to Find the CORRECT Avatar ID

**Step 1: Use the API to list your avatars**
```bash
curl -X GET https://api.heygen.com/v2/avatars \
  -H "X-Api-Key: YOUR_API_KEY"
```

**Step 2: Look for YOUR avatar in the response**
The response contains groups and avatars:
```json
{
  "data": {
    "avatars": [
      {
        "avatar_id": "abc123def456...",  // ← USE THIS (32 chars, no dashes)
        "avatar_name": "My Custom Avatar",
        "preview_image_url": "...",
        "preview_video_url": "..."
      }
    ]
  }
}
```

### Common Mistakes

| Wrong ID | Why It's Wrong | Correct ID |
|----------|----------------|------------|
| `Daisy-inskirt-20220818` | Stock avatar name, not ID | Get ID from API response |
| `avatar_group_12345` | This is a GROUP ID | Use individual avatar_id |
| `a1b2-c3d4-e5f6...` | Format with dashes | Should be 32 hex chars, no dashes |
| `My Avatar Name` | Display name, not ID | Use the avatar_id field |

### Quick Validation Checklist
- [ ] Avatar ID is 32 hexadecimal characters (no dashes, no spaces)
- [ ] Avatar ID is from `/v2/avatars` response, not HeyGen dashboard URL
- [ ] For custom avatars: check the avatar was fully processed (not pending)
- [ ] For stock avatars: use the API to get the exact ID

### API Test Command
```bash
# Test if your avatar ID is valid
curl -X POST https://api.heygen.com/v2/video/generate \
  -H "X-Api-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "video_inputs": [{
      "character": {
        "type": "avatar",
        "avatar_id": "YOUR_AVATAR_ID_HERE",
        "avatar_style": "normal"
      },
      "voice": {
        "type": "text",
        "input_text": "Hello, this is a test.",
        "voice_id": "YOUR_VOICE_ID"
      }
    }],
    "dimension": {"width": 720, "height": 1280}
  }'
```

If you get `{"data":{"video_id":"..."}}` → Avatar ID is correct
If you get `400 Bad Request` → Avatar ID is wrong

**Auto-Fix Rule:** Detect HeyGen HTTP nodes → Validate avatar_id format (32 hex chars)

---

## 53. HeyGen: CRITICAL - Avatar Type Confusion (Talking Photo vs Video Avatar)
**Problem:** Using wrong avatar type in API - most common HeyGen mistake that wastes HOURS!
**Error:** `avatar_not_found` even though avatar exists in HeyGen dashboard
**Detection:** HeyGen API calls

### STOP - FIRST QUESTION: What type of avatar did you create?

HeyGen has THREE different avatar types with DIFFERENT API calls:

| Type | How You Created It | API `type` | API ID Field | List Endpoint |
|------|-------------------|------------|--------------|---------------|
| **Talking Photo** | Uploaded a PHOTO | `talking_photo` | `talking_photo_id` | `/v1/talking_photo.list` |
| **Video Avatar** | Uploaded 2+ min VIDEO | `avatar` | `avatar_id` | `/v2/avatars` |
| **Public Avatar** | Pre-made (Alex, Anna) | `avatar` | `avatar_id` | `/v2/avatars` |

### How to Check What You Have

**List your Talking Photos:**
```bash
curl -X GET https://api.heygen.com/v1/talking_photo.list \
  -H "X-Api-Key: YOUR_API_KEY"
```

**List your Video/Public Avatars:**
```bash
curl -X GET https://api.heygen.com/v2/avatars \
  -H "X-Api-Key: YOUR_API_KEY"
```

### Correct API Payload for Each Type

**For Talking Photo (created from a photo):**
```python
"character": {
    "type": "talking_photo",
    "talking_photo_id": "YOUR_TALKING_PHOTO_ID"
}
```

**For Video Avatar or Public Avatar:**
```python
"character": {
    "type": "avatar",
    "avatar_id": "YOUR_AVATAR_ID",
    "avatar_style": "normal"
}
```

### Common Symptom - THE HOUR-WASTING TRAP
- You see your avatar in HeyGen dashboard ✓
- You copied the ID correctly ✓
- But API returns `avatar_not_found` ✗
- **ROOT CAUSE: You're using `type: avatar` for a Talking Photo!**

### Quick Fix
1. Check which list endpoint returns your avatar ID
2. If it's in `/v1/talking_photo.list` → use `type: talking_photo` + `talking_photo_id`
3. If it's in `/v2/avatars` → use `type: avatar` + `avatar_id`

**Auto-Fix Rule:** Detect HeyGen nodes → Ask user "Did you create your avatar from a PHOTO or a VIDEO?"

---

# BLOTATO PUBLISHING GOTCHAS

> **Source:** Blotato Help Documentation (https://help.blotato.com/support/errors)
> **Use Case:** Posting AI-generated videos to social platforms via Blotato API

## 54. Blotato: Authorization Failed
**Problem:** API key invalid or malformed
**Error:** "Authorization failed - please check your credentials" or "Wrong Blotato API Key"
**Detection:** HTTP 401 from Blotato endpoints
**Fix:**
- Check API key copied correctly without whitespace
- API key format: `blt_` prefix followed by base64 string
- Verify key at https://my.blotato.com/settings/api-keys

**Auto-Fix Rule:** Validate Blotato API key format → Flag if missing `blt_` prefix

---

## 55. Blotato: Wrong Account ID
**Problem:** Social account ID doesn't match connected account
**Error:** "Wrong Account ID"
**Detection:** HTTP 400 on post requests
**Fix:**
- Go to Blotato dashboard → Settings → Social Accounts
- Click "Copy Account ID" for each platform
- For Facebook: Need BOTH Account ID AND Page ID

```python
# ❌ WRONG - Using page ID as account ID
BLOTATO_FACEBOOK_ACCOUNT_ID = "719899667869698"  # This is a page ID!

# ✅ CORRECT - Account ID is different from Page ID
BLOTATO_FACEBOOK_ACCOUNT_ID = "16601"
BLOTATO_FACEBOOK_PAGE_ID = "719899667869698"
```

**Auto-Fix Rule:** Detect Facebook posts → Verify both accountId and pageId are set

---

## 56. Blotato: URL is Empty / mediaURL is null
**Problem:** Video URL not ready when posting (HeyGen still processing)
**Error:** "URL is empty" or "mediaURL is null or empty"
**Detection:** Empty string in mediaUrls array
**Fix:**
- Increase wait time for video generation (HeyGen takes 3-8 minutes)
- Check HeyGen video status before posting
- Verify you have AI credits (video generation fails silently without credits)

```python
# ✅ CORRECT - Poll until video is ready
async def wait_for_video(video_id: str, max_attempts: int = 30, delay: int = 60):
    for attempt in range(max_attempts):
        status = await get_heygen_video_status(video_id)
        if status.status == "completed":
            return status.video_url  # Only return when URL exists
        await asyncio.sleep(delay)
```

**Auto-Fix Rule:** Detect Blotato post with mediaUrls → Warn if URL could be empty

---

## 57. Blotato: Rate Limits
**Problem:** Too many requests too fast
**Error:** "The service is receiving too many requests from you"
**Detection:** HTTP 429 response
**Limits:**
- Upload Media: 10 requests/minute
- Publish Post: 30 requests/minute

**Fix:** Add delays between requests, especially when posting to multiple platforms

**Auto-Fix Rule:** Detect multiple Blotato posts in sequence → Suggest adding delays

---

## 58. Blotato: Platform Posting Limits
**Problem:** Exceeded daily posting limits per platform
**Detection:** Post fails after successful API call

| Platform | Daily Limit | Notes |
|----------|-------------|-------|
| TikTok (Starter) | 10 posts/account | Creator/Agency plans unrestricted |
| Instagram | 50 posts/account | Hard limit per 24h |
| Pinterest | 10 pins/account | Must be validated by Blotato team |
| YouTube | Variable | New channels have low API quota |

**Fix:** Track posts per platform, don't exceed limits
**Auto-Fix Rule:** Count posts per platform → Warn when approaching limits

---

## 59. Blotato: Invalid Video Format/Dimensions
**Problem:** Video doesn't meet platform requirements
**Error:** "Invalid File Format" or "Invalid Video Dimensions" or "The aspect ratio is not supported"
**Detection:** HTTP 400 on upload or post
**Platform Requirements:**
- TikTok: 9:16 aspect ratio, MP4, max 10 minutes
- Instagram Reels: 9:16, MP4, 3-90 seconds
- YouTube Shorts: 9:16, MP4, max 60 seconds
- Pinterest: Various ratios supported

**Test URL:** https://database.blotato.io/storage/v1/object/public/public_media/4ddd33eb-e811-4ab5-93e1-2cd0b7e8fb3f/videogen-4c61a730-7eb2-47e9-a3a3-524740a1b877.mp4

**Auto-Fix Rule:** Check video dimensions before posting → Flag non-9:16 for TikTok/Reels

---

## 60. Blotato: File Too Large
**Problem:** Video exceeds upload size limit
**Error:** "Base64 data is too large, maximum size is 20MB" or "Failed to read media metadata"
**Detection:** Large video files (>15MB)
**Fix:**
- Use URL-based upload instead of binary/base64
- For videos >50MB, use cloud storage (AWS S3, GCP) instead of Google Drive
- HeyGen videos are typically 5-15MB, should be fine

```python
# ✅ CORRECT - Use URL upload, not binary
async def upload_to_blotato(video_url: str) -> str:
    response = await client.post(
        "https://backend.blotato.com/v2/media",
        json={"url": video_url}  # URL-based, not binary
    )
```

**Auto-Fix Rule:** Detect binary uploads → Suggest URL-based upload

---

## 61. Blotato: TikTok URL Ownership Verification
**Problem:** TikTok rejects certain video hosting URLs
**Error:** "Please review our URL ownership verification rules"
**Detection:** TikTok posts failing with URL errors
**Fix:**
- Upload video to Blotato first using `/v2/media` endpoint
- Use the returned Blotato-hosted URL for posting
- Avoid direct Google Drive or Dropbox links

**Auto-Fix Rule:** Detect TikTok posts with non-Blotato URLs → Suggest upload first

---

## 62. Blotato: TikTok Shadowban Indicators
**Problem:** TikTok limiting reach on account
**Detection:** Consistent patterns in view counts
**Indicators:**
- Views consistently <50 = Likely shadowbanned → Start fresh account
- Views consistently ~200 = Topic not recognized → Add niche keywords to title/description/audio
- Account banned = Not warmed up → Follow warm-up guide, max 3 posts/day via API

**Fix:**
1. Warm up new accounts with manual posts for several days
2. Stay active (reply to comments, engage)
3. Don't exceed 3 posts/day via API
4. Use `isAIGenerated: true` for AI content disclosure

---

## 63. Blotato: Instagram Spam Restriction
**Problem:** Instagram flagging account as spam/bot
**Error:** "We restrict certain activity to protect our community" or "Error posting to Instagram: No error"
**Detection:** Instagram posts failing
**Fix:**
1. Reduce number of hashtags (max 5-10)
2. Reduce caption length
3. Increase time between posts (2+ hours)
4. Post manually to warm up account
5. Engage with other accounts (like, comment, follow)

**Auto-Fix Rule:** Detect Instagram posts → Warn about warm-up requirements

---

## 64. Blotato: Threads Not Connected
**Problem:** Threads requires linked Instagram and warm-up
**Error:** "Threads API Feature Not Available: This user does not have access to this Threads API feature"
**Detection:** Threads posts failing
**Fix:**
1. Link Instagram account to Threads in the Threads app
2. Post manually on Threads for several days
3. Then connect to Blotato

**Auto-Fix Rule:** Detect Threads platform → Warn about warm-up requirement

---

## 65. Blotato: General Connection Issues
**Problem:** Can't connect social account to Blotato
**Error:** "400 Session Error", "Unable to connect", "Unauthorized"
**Fix (Universal Workaround):**
1. Open incognito Chrome browser
2. Log out of ALL other accounts
3. Log into target social account ONLY
4. Log into Blotato
5. Connect account

**Platform-Specific:**
- LinkedIn Company Page: Must be Admin of the page
- YouTube: Reconnect and update account ID in workflows
- Facebook: Need page admin access

---

## 66. Blotato: Troubleshooting Checklist
**When posts aren't going through:**

1. **Check Failed Dashboard:** https://my.blotato.com/failed
2. **Verify API Key:** No whitespace, starts with `blt_`
3. **Check Credits:** Settings > Billing
4. **Validate JSON:** Use jsonlint.com
5. **Test with Sample Video:** Use Blotato's test video URL
6. **Check Account Warm-up:** New accounts need manual posts first
7. **Review Rate Limits:** Not exceeding 10 uploads/min or 30 posts/min

**Debug API Call:**
```bash
curl -X POST https://backend.blotato.com/v2/posts \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "post": {
      "accountId": "YOUR_ACCOUNT_ID",
      "content": {
        "text": "Test post",
        "mediaUrls": ["https://database.blotato.io/storage/v1/object/public/public_media/4ddd33eb-e811-4ab5-93e1-2cd0b7e8fb3f/videogen-4c61a730-7eb2-47e9-a3a3-524740a1b877.mp4"],
        "platform": "tiktok"
      },
      "target": {"targetType": "tiktok", "isAIGenerated": true}
    }
  }'
```

---

# SHIPFLOW CONVERSION GOTCHAS

> **Source:** Lessons learned from converting n8n workflows to Python/FastAPI
> **Added:** December 2024

## 67. ShipFlow: Missing Platform-Specific API Fields
**Problem:** When converting Blotato nodes, platform-specific required fields get missed
**Error:** `400 Bad Request` with `"must have required property 'boardId'"` or similar
**Detection:** Blotato API nodes with platform-specific parameters

### What Gets Missed

The n8n Blotato node has platform-specific parameters like:
```json
"pinterestBoardId": { "value": "1234" }
"facebookPageId": { "value": "123456789" }
"postCreateYoutubeOptionTitle": "Video Title"
"postCreateTiktokOptionIsAiGenerated": true
```

These translate to REQUIRED fields in the Blotato API:

| n8n Parameter | API Payload Field | Platform |
|--------------|-------------------|----------|
| `pinterestBoardId` | `target.boardId` | Pinterest (REQUIRED!) |
| `facebookPageId` | `target.pageId` | Facebook (REQUIRED!) |
| `postCreateYoutubeOptionTitle` | `target.title` | YouTube |
| `postCreateYoutubeOptionContainsSyntheticMedia` | `target.containsSyntheticMedia` | YouTube |
| `postCreateTiktokOptionIsAiGenerated` | `target.isAIGenerated` | TikTok |

### Fix
ShipFlow must extract ALL parameters matching these patterns:
- `pinterestBoardId` → `target.boardId`
- `facebookPageId` → `target.pageId`
- `postCreate[Platform]Option*` → corresponding payload fields

### Prevention Checklist
- [ ] When converting Blotato nodes, list ALL platforms being posted to
- [ ] Check each platform for required fields
- [ ] Generate .env variables for all required IDs
- [ ] Add TODO comments for user to fill in missing IDs

**Auto-Fix Rule:** Generate checklist of platform-specific fields during conversion

---

## 68. ShipFlow: Node-Level Retry Settings Not Converted
**Problem:** n8n nodes have retry settings that aren't converted to Python
**Error:** API calls fail that would have succeeded with retries (transient failures, race conditions)
**Detection:** Any node with `retryOnFail: true`

### What Gets Missed

n8n nodes can have retry settings at the node level:
```json
{
  "name": "Instagram [BLOTATO]",
  "retryOnFail": true,
  "maxTries": 2,
  "waitBetweenTries": 5000,
  "parameters": { ... }
}
```

These settings tell n8n to retry the node if it fails.

### Fix
Wrap converted functions in retry logic that matches the n8n settings:

```python
async def call_with_retry(func, max_retries=2, delay_ms=5000):
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(delay_ms / 1000)
            else:
                raise
```

### Detection During Conversion
ShipFlow should scan EVERY node for these fields:
- `retryOnFail` (boolean)
- `maxTries` (integer)
- `waitBetweenTries` (milliseconds)

### Why This Matters
Many API integrations have transient failures:
- HeyGen video not ready yet
- Blotato rate limits
- Network hiccups
- OAuth token refresh timing

Without retry logic, workflows that worked in n8n will fail in Python.

**Auto-Fix Rule:** Detect retryOnFail → Generate retry wrapper with matching maxTries/waitBetweenTries

---

## 69. ShipFlow: Conditional Loops (If → Wait → Check) Not Properly Converted
**Problem:** n8n "If" nodes that loop back to "Wait" nodes create polling patterns that need explicit conversion
**Error:** Video posted before it's ready, or workflow waits forever
**Detection:** Check connections - if "If" node's FALSE output connects back to an earlier "Wait" node

### The Pattern in n8n

```
Wait → Get Status → If Done?
                      ↓ TRUE → Continue
                      ↓ FALSE → Back to Wait (LOOP!)
```

This is the "wait and retry" pattern for async operations like video generation.

### Correct Python Conversion

```python
async def wait_for_video_completion(video_id: str, max_attempts: int = 30, delay: int = 60):
    """Polling loop that matches n8n's Wait → Check → Loop pattern"""
    for attempt in range(max_attempts):
        status = await get_video_status(video_id)

        if status.status == "completed":
            return status.video_url

        if status.status == "failed":
            raise Exception("Video generation failed")

        # Loop back (this is the FALSE branch going to Wait)
        await asyncio.sleep(delay)

    raise TimeoutError("Video generation timed out")
```

### Detection During Conversion
Look for this pattern in the workflow connections:
1. "Wait" node followed by status check
2. "If" node after status check
3. "If" FALSE output connects back to the Wait node

**Auto-Fix Rule:** Detect If→Wait loops → Generate proper polling function

---

# TEMPLATE FOR NEW GOTCHAS

When you discover a new issue, add it here using this format:

```markdown
## [NUMBER]. [SHORT TITLE]
**Problem:** What goes wrong (1-2 sentences)
**Error:** Exact error message or behavior
**Detection:** How to spot this in the JSON or workflow
**Fix:** How to resolve it (steps or code example)
**Auto-Fix Rule:** What the validator should do automatically
```

---

# PRE-FLIGHT VALIDATION CHECKLIST

Before importing ANY workflow, verify:

- [ ] No `$env.` references (unless self-hosted)
- [ ] No deprecated AI models
- [ ] No hardcoded API keys in workflow JSON
- [ ] Webhook has Production URL (not Test)
- [ ] Webhook has custom path (not UUID)
- [ ] All nodes are connected (no orphans)
- [ ] First node is a trigger
- [ ] Error workflow is configured
- [ ] Supabase has both required headers
- [ ] HTTP requests have correct Content-Type
- [ ] Code nodes return proper array format
- [ ] AI Agent has memory connected (if needed)

---

## REFERENCES

- [n8n Docs - Common Issues](https://docs.n8n.io/)
- [n8n Community Forum](https://community.n8n.io/)
- [n8n GitHub Issues](https://github.com/n8n-io/n8n/issues)

---

# PYTHON BACKEND GOTCHAS

## 70. Python Server Wrong Working Directory / .env Not Loading
**Problem:** Python uvicorn server started from wrong directory doesn't load `.env` file correctly
**Symptoms:**
- Server runs but uses wrong/old environment variable values
- Validation shows "Avatar ID Format" instead of "Talking Photo ID Format" (wrong avatar type)
- `/heygen/talking-photos` endpoint shows different `current_id` than what's in `.env`
- API calls fail even though `.env` has correct keys

**Detection:**
1. Check `/config` endpoint - compare with actual `.env` values
2. Check `/validate` endpoint - look for "Talking Photo" vs "Avatar" in check names
3. Config values don't match what's in the `.env` file

**Root Cause:**
- Server was started from wrong directory (Docker, VS Code terminal, background process)
- `load_dotenv()` loads from current working directory, not app directory
- Old server process still running with cached environment

**Fix:**
```bash
# 1. Find and kill the running server
netstat -ano | findstr 8000  # Get PID
taskkill /PID <pid> /F       # Kill it

# 2. Start server from CORRECT directory
cd c:\Projects\shipflow-app\backend
python -m uvicorn app:app --host 0.0.0.0 --port 8000

# Or via PowerShell (handles Windows paths better)
powershell -Command "Set-Location 'c:\Projects\shipflow-app\backend'; python -m uvicorn app:app --host 0.0.0.0 --port 8000"
```

**Verification:**
```bash
# After restart, verify correct values loaded
curl http://localhost:8000/heygen/talking-photos | jq '.current_id'
# Should match HEYGEN_TALKING_PHOTO_ID in .env
```

**Auto-Fix Rule:** Compare `/config` response with `.env` file → Flag mismatch

---

## ADD YOUR GOTCHAS BELOW:

<!-- When you discover new issues, add them here! -->
