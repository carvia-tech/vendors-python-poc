# TODO: Geo-Context + AI Result Selection for Same-Name Company Disambiguation

## Branch: `feature/fastapiv2`

## Overview
Two-phased disambiguation approach:
1. **Phase 1 - Geo-Context:** Region-aware search queries + TLD scoring to prioritize local results
2. **Phase 2 - AI Result Selection:** When confidence is low, use LLM to pick the correct website from top candidates

## Files to Create:
1. **services/disambiguator.py** - New service for AI-powered result selection

## Files to Modify:
1. **schemas/request.py** - Add `region` & `country` fields to `EnrichmentRequest`
2. **config.py** - Add geo search settings, regional domain map, disambiguation config
3. **services/search.py** - Add geo-context to search queries, TLD scoring, return multiple candidates
4. **api/routes/enrichment.py** - Pass geo params through pipeline
5. **api/dependencies.py** - Pass geo params through enrichment pipeline + call disambiguator
6. **app.py** - Add geo + disambiguation UI elements

## Detailed Steps:

### Step 1: Create `services/disambiguator.py` (NEW FILE)
- `DisambiguatorService` class
- `disambiguate_company(company_name, candidates, region, ai_api_key)` method
- Builds a prompt with candidate URLs + scraped snippets → asks LLM to pick the best one
- Returns the selected URL with confidence score + reasoning
- Falls back to first candidate if AI is unavailable

### Step 2: Update Request Schema (`schemas/request.py`)
- Add optional `region: Optional[str]` field (e.g., "India", "USA", "Europe")
- Add optional `country: Optional[str]` field (e.g., "IN", "US", "GB")

### Step 3: Update Config (`config.py`)
- Add `REGION_TLD_MAP` - maps regions to TLDs for scoring:
  ```python
  REGION_TLD_MAP = {
      "india": [".in", ".co.in"],
      "usa": [".com", ".us"],
      "uk": [".co.uk", ".uk"],
      "germany": [".de"],
      "france": [".fr"],
      "japan": [".co.jp", ".jp"],
  }
  ```
- Add `disambiguation_min_confidence: int = 70` - threshold to trigger AI selection
- Add `disambiguation_max_candidates: int = 5`

### Step 4: Enhance Search Service (`services/search.py`)
- Modify `search_official_website()` to accept `region: Optional[str]` and `country: Optional[str]`
- Build geo-aware search queries (try in order):
  1. `"{company_name} {region} official website"`
  2. `"{company_name} {region}"`
  3. `"{company_name} official website"` (generic fallback)
- Add TLD-based region scoring in `_is_official_site()`:
  - If `region="India"` and TLD is `.in` → boost score +20
  - If `region="India"` and TLD is `.com` → neutral
- Add `search_top_candidates()` method that returns top N scored results instead of just 1
- Add scoring system:
  - Domain authority: +10 for .com/.org/.io
  - TLD matches region: +30
  - Company name in URL: +20
  - No 'official' in description: -10
  - Social/excluded patterns: -50

### Step 5: Update Dependencies (`api/dependencies.py`)
- Update `run_enrichment_pipeline()` to accept `region` and `country` params
- If AI API key is available AND confidence is low → call `DisambiguatorService`
- Pass geo params to search service

### Step 6: Update Enrichment Route (`api/routes/enrichment.py`)
- Pass `region` and `country` from `EnrichmentRequest` to pipeline

### Step 7: Update Streamlit App (`app.py`)
- Add region input (text field or dropdown) in sidebar
- Add country input in sidebar
- Display disambiguation confidence in results
- Show which approach was used (geo-only vs AI-assisted)

## Disambiguation Pipeline Flow:
```
Request: { company_name: "Amazon", region: "India", api_key: "sk-..." }

Step 1: Search with geo queries
  → Query 1: "Amazon India official website"
  → Query 2: "Amazon India"
  → Query 3: "Amazon official website" (fallback)

Step 2: Score & rank all results
  → 1. amazon.in (score: 85) ← TLD matches India!
  → 2. amazon.com (score: 65)
  → 3. amazon.jobs (score: 40)

Step 3: If top score > 70 → use it directly
         Else → call AI to disambiguate

Step 4: Return final URL with confidence metadata
```

## Testing Scenarios:
- "Amazon" + region="India" → amazon.in (geo match, high confidence)
- "Amazon" + region="USA" → amazon.com (geo match)
- "Amazon" + no region → amazon.com (generic fallback, current behavior)
- "Infosys" + region="India" → infosys.com (geo match)
- "Reliance" + region="India" → relianceindustries.com (geo-assisted)
- "Reliance" + no region → could be wrong → AI selection helps
- Backward compatibility: no region → works exactly as before

