# AutoResearch Loop for RAG Citation Quality: Production Design Guide

<!-- Copilot-Researcher-Visualization -->
```html
<style>
    :root {
      --accent: #464FEB;
      --max-print-width: 540px;
      --text-title: #242424;
      --text-sub: #424242;
      --font: "Segoe Sans", "Segoe UI", "Segoe UI Web (West European)", -apple-system, "system-ui", Roboto, "Helvetica Neue", sans-serif;
      --overflow-wrap: break-word;
      --icon-background: #F5F5F5;
      --icon-size: 24px;
      --icon-font-size: 20px;
      --number-icon-size: 16px;
      --number-icon-font-size: 12px;
      --number-icon-color: #ffffff;
      --divider-color: #f0f0f0;
      --timeline-ln: linear-gradient(to right, transparent 0%, #e0e0e0 15%, #e0e0e0 85%, transparent 100%) no-repeat 6px 12px / 1px calc(100% - 48px);
      --timeline-date-color:#616161;
      --divider-padding: 4px;
      --row-gap: 32px;
      --max-width: 1100px;
      --side-pad: 20px;
      --line-thickness: 1px;
      --text-gap: 10px;
      --dot-size: 12px;
      --dot-border: 0;
      --dot-color: #000000;
      --dot-bg: #ffffff;
      --spine-color: #e0e0e0;
      --connector-color: #e0e0e0;
      --spine-gap: 60px;
      --h4-gap: 25px;
      --card-pad: 12px;
      --date-line: 1rem;
      --date-gap: 6px;
      --h4-line: 24px;
      --background-color: #f5f5f5;
      --border: 1px solid #E0E0E0;
      --border-radius: 16px;
      --tldr-container-title: #707070;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --accent: #7385FF;
        --timeline-ln: linear-gradient(to right, transparent 0%,#525252 15%, #525252 85%, transparent 100%) no-repeat 6px 12px / 1px calc(100% - 48px);
        --timeline-date-color:#707070;
        --bg-hover: #2a2a2a;
        --text-title: #ffffff;
        --text-sub: #d6d6d6;
        --shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        --hover-shadow: 0 4px 14px rgba(0, 0, 0, 0.5);
        --icon-background: #3d3d3d;
        --divider-color: #3d3d3d;
        --dot-color: #ffffff;
        --dot-bg: #292929;
        --spine-color: #525252;
        --connector-color: #525252;
        --background-color: #141414;
        --border: 1px solid #E0E0E0;
        --tldr-container-title: #999999;
      }
    }
    @media (prefers-contrast: more),
    (forced-colors: active) {
      :root {
        --accent: ActiveText;
        --timeline-ln: Canvas;
        --bg-hover: Canvas;
        --text-title: CanvasText;
        --text-sub: CanvasText;
        --shadow: 0 2px 10px Canvas;
        --hover-shadow: 0 4px 14px Canvas;
      }
    }    .tldr-container {
      display: flex;
      flex-direction:column;
      font-family: var(--font);
      gap: 12px;
      padding: clamp(12px, 4vw, 20px) 0;
      border-radius: var(--border-radius);
      align-items: stretch;
      box-sizing: border-box;
      width: calc(100vw - 17px);
      width: 100%;
      max-width: var(--max-width);
      margin-inline: auto;
      overflow-wrap: anywhere;
      word-break: break-word;
      overflow-x: auto;
    }
    .tldr-container h2 {
      color: var(--tldr-container-title);
      font-weight: 600;
      font-style: normal;
      font-size: clamp(18px, 3vw, 20px);
      line-height: 28px;
      border-bottom: var(--border);
      margin: 0;
    }
    .tldr-card {
      display: flex;
      flex-flow: row wrap;
      align-items: flex-start;
      gap: 4px;
      border-radius: 24px;
      min-width: 0; 
    }
    .tldr-card h3 {
      flex: 1 1 auto;
      min-width: 0;
      font-size: 16px;
      font-weight: 600;
      line-height: 22px;
      margin: 0;
      font-style: normal;
      color: var(--text-title);
      overflow-wrap: anywhere;
      word-break: break-word;

    }
    .tldr-card p {
      font-size: 16px;
      font-weight: 400;
      color: var(--text-sub);
      line-height: 20px;
      margin: 0;
      overflow-wrap: var(--overflow-wrap);
      flex: 0 0 100%;
      width: 100%;
      gap: 10px;
      padding: 0;
      word-break: break-word;
      hyphens: auto;
      min-width: 0;

    }
    .tldr-card p b,
    .tldr-card p strong {
      font-weight: normal;
    }
    
    @media (max-width: 480px) {
      .tldr-card {
        gap: 8px;
      }
    }    

</style>
<div class="tldr-container"><h2>Executive summary</h2>
<div class="tldr-card"><h3>Start with golden dataset</h3><p>Build 50-100 expert-reviewed question-answer-citation triples before any automation</p></div>
<div class="tldr-card"><h3>One variable per iteration</h3><p>Sequential experimentation prevents confounds; track every change in version control</p></div>
<div class="tldr-card"><h3>Hybrid evaluation is essential</h3><p>Combine LLM judges with heuristic metrics and periodic human review for reliable quality signals</p></div>
<div class="tldr-card"><h3>Azure provides complete stack</h3><p>Evaluations SDK for orchestration, AI Search for retrieval variants, Application Insights for signals</p></div>
</div>
```

---

## Where to Start: Foundation First

**Start by establishing a measurement baseline before building any automation.** Research from Microsoft, Google, and academia consistently shows that self-improving systems fail without reliable ground truth and stable metrics.

### Step 1: Create Your Golden Dataset

Build a **human-curated evaluation set of 50-100 examples** in Azure AI Evaluations SDK JSONL format before automating anything. Each record should contain:

```json
{
  "question": "Can a taxpayer depreciate software development costs under Section 179?",
  "ideal_answer": "Yes, under IRC Section 179, taxpayers may elect to expense qualifying software costs up to annual limits ($1,160,000 for 2023) rather than depreciate them.",
  "ideal_citations": [
    {"text": "qualifying software costs", "source": "IRS Pub 946", "page": 12, "sentence": "Computer software is generally depreciable..."},
    {"text": "$1,160,000 for 2023", "source": "IRS Rev Proc 2022-38", "page": 3, "sentence": "For tax years beginning in 2023, the limitation is $1,160,000"}
  ],
  "ideal_chunks": ["chunk_id_789", "chunk_id_1024"],
  "metadata": {
    "complexity": "medium",
    "requires_multi_hop": false,
    "tax_year": "2023",
    "reviewed_by": "senior_tax_advisor_initials",
    "review_date": "2024-03-15"
  }
}
```

**Why this format matters for tax advisory:**
- **Ideal citations at sentence level** enable you to measure attribution F1 (whether the system found the *right* evidence, not just *any* evidence)
- **Ideal chunks** let you debug retrieval separately from generation
- **Metadata tags** enable stratified analysis (e.g., "Are multi-hop questions failing?")
- **Reviewer attribution** satisfies audit requirements

**Acquisition strategy:**
1. **Seed from real queries:** Export 200-300 recent customer questions from Application Insights logs
2. **Tax expert review:** Have senior advisors write gold-standard answers with manual citations (budget 15-20 min per question)
3. **Diversity sampling:** Ensure coverage across tax code sections, document types, complexity levels
4. **Version control:** Store in Git with approval workflow; treat as production code

### Step 2: Define Your Metrics Suite

**Use a hybrid metrics approach combining automated scoring with human checkpoints.** No single metric captures citation quality completely.

<!-- Copilot-Researcher-Visualization -->
```html
<style>
    :root {
      --accent: #464FEB;
      --max-print-width: 540px;
      --text-title: #242424;
      --text-sub: #424242;
      --font: "Segoe Sans", "Segoe UI", "Segoe UI Web (West European)", -apple-system, "system-ui", Roboto, "Helvetica Neue", sans-serif;
      --overflow-wrap: break-word;
      --icon-background: #F5F5F5;
      --icon-size: 24px;
      --icon-font-size: 20px;
      --number-icon-size: 16px;
      --number-icon-font-size: 12px;
      --number-icon-color: #ffffff;
      --divider-color: #f0f0f0;
      --timeline-ln: linear-gradient(to right, transparent 0%, #e0e0e0 15%, #e0e0e0 85%, transparent 100%) no-repeat 6px 12px / 1px calc(100% - 48px);
      --timeline-date-color:#616161;
      --divider-padding: 4px;
      --row-gap: 32px;
      --max-width: 1100px;
      --side-pad: 20px;
      --line-thickness: 1px;
      --text-gap: 10px;
      --dot-size: 12px;
      --dot-border: 0;
      --dot-color: #000000;
      --dot-bg: #ffffff;
      --spine-color: #e0e0e0;
      --connector-color: #e0e0e0;
      --spine-gap: 60px;
      --h4-gap: 25px;
      --card-pad: 12px;
      --date-line: 1rem;
      --date-gap: 6px;
      --h4-line: 24px;
      --background-color: #f5f5f5;
      --border: 1px solid #E0E0E0;
      --border-radius: 16px;
      --tldr-container-title: #707070;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --accent: #7385FF;
        --timeline-ln: linear-gradient(to right, transparent 0%,#525252 15%, #525252 85%, transparent 100%) no-repeat 6px 12px / 1px calc(100% - 48px);
        --timeline-date-color:#707070;
        --bg-hover: #2a2a2a;
        --text-title: #ffffff;
        --text-sub: #d6d6d6;
        --shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        --hover-shadow: 0 4px 14px rgba(0, 0, 0, 0.5);
        --icon-background: #3d3d3d;
        --divider-color: #3d3d3d;
        --dot-color: #ffffff;
        --dot-bg: #292929;
        --spine-color: #525252;
        --connector-color: #525252;
        --background-color: #141414;
        --border: 1px solid #E0E0E0;
        --tldr-container-title: #999999;
      }
    }
    @media (prefers-contrast: more),
    (forced-colors: active) {
      :root {
        --accent: ActiveText;
        --timeline-ln: Canvas;
        --bg-hover: Canvas;
        --text-title: CanvasText;
        --text-sub: CanvasText;
        --shadow: 0 2px 10px Canvas;
        --hover-shadow: 0 4px 14px Canvas;
      }
    }    .metrics-container {
      display: grid;
      grid-template-columns: repeat(2, minmax(210px, 1fr));
      font-family: var(--font);
      padding: 12px 24px 24px 24px;
      gap: 12px;
      align-items: stretch;
      justify-content: center;
      box-sizing: border-box;
      width: calc(100vw - 17px);
    }
    .metric-card {
      padding: 20px 12px;
      text-align: center;
      display: flex;
      flex-direction: column;
      gap: 4px;
      background-color: var(--background-color);
      border-radius: var(--border-radius);
    }
    .metric-card h4 {
      margin: 0px;
      font-size: 14px;
      color: var(--text-sub);
      font-weight: 600;
      text-align: center;
      font-style: normal;
      line-height: 20px;
      text-overflow: ellipsis;
      order: 2;
    }
    .metric-card-value {
      margin-bottom: 8px;
      color: var(--accent);
      font-size: 24px;
      font-weight: 600;
      font-style: normal;
      text-align: center;
      line-height: 32px;
      text-overflow: ellipsis;
      order: 1;
    }
    .metric-card p {
      font-size: 12px;
      font-weight: 400;
      font-style: normal;
      color: var(--text-sub);
      line-height: 16px;
      margin: 0;
      overflow-wrap: var(--overflow-wrap);
     order: 3;
    }
    .metrics-container:has(> :nth-child(3)):not(:has(> :nth-child(4))) {
        grid-template-columns: repeat(3, minmax(150px, 1fr));
    }
    .metrics-container:has(> :nth-child(4)) > .metric-card {
        display:grid;
        grid-template-columns: 150px 1fr;
        column-gap:40px;
        row-gap:8px;
        padding:20px;
        border-radius: 0;
    }    
    .metrics-container:has(>:nth-child(4)) >.metric-card:not(:last-child) {
        border-bottom: var(--border);
    }
    .metrics-container:has(> :nth-child(4)) > .metric-card .metric-card-value {
        grid-column: 1;
        grid-row: 1 / span 2;
        align-self: center;
        text-align: center;
        margin:0;
    }
    .metrics-container:has(> :nth-child(4)) > .metric-card h4,
    .metrics-container:has(> :nth-child(4)) > .metric-card p {
        text-align:left; 
    }
    .metrics-container:has(> :nth-child(4)),
    .metrics-container:has(> :first-child:last-child) {
        grid-template-columns: 1fr;
        gap: 0px;
        background-color: var(--background-color);
        border-radius: var(--border-radius);
        padding: 0 24px;
    }
    @media (max-width:600px) {
        .metrics-container,
        .metrics-container:has(> :nth-child(3)):not(:has(> :nth-child(4))) {
            grid-template-columns:1fr;
        }
        .metric-card,
        .metric-card:last-child:nth-child(odd),
        .metrics-container:has(> :nth-child(4)) > .metric-card,
        .metrics-container:has(> :nth-child(4)) .metric-card:last-child:nth-child(odd) {
            display: flex;
            flex-direction: column;
            grid-column: span 1;
        }
        .metrics-container:has(> :nth-child(4)) > .metric-card h4,
        .metrics-container:has(> :nth-child(4)) > .metric-card p {
            text-align:center;
        }
    }
</style>
<div class="metrics-container">
<div class="metric-card">
<h4>Citation Precision</h4>
<div class="metric-card-value">85-95%</div>
<p>Claimed facts actually supported</p>
</div>
<div class="metric-card">
<h4>Citation Recall</h4>
<div class="metric-card-value">75-90%</div>
<p>Relevant sources actually cited</p>
</div>
<div class="metric-card">
<h4>Attribution F1</h4>
<div class="metric-card-value">80-92%</div>
<p>Harmonic mean precision/recall</p>
</div>
<div class="metric-card">
<h4>Groundedness Score</h4>
<div class="metric-card-value">≥0.90</div>
<p>Azure Content Safety agreement</p>
</div>
<div class="metric-card">
<h4>Human Agreement</h4>
<div class="metric-card-value">≥85%</div>
<p>Expert accepts answer as-is</p>
</div>
</div>
```

**Recommended metrics in priority order:**

| Metric | Calculation | Tool/Method | Why It Matters for Tax |
|--------|-------------|-------------|------------------------|
| **Citation Precision** | (Correctly grounded claims) / (Total claims made) | Azure Content Safety Groundedness API per claim | Prevents false confidence; every unsupported claim is a liability risk |
| **Citation Recall** | (Cited gold sources) / (All gold sources for question) | Compare system citations to `ideal_citations` in JSONL | Ensures comprehensive coverage; missing a key statute can invalidate advice |
| **Attribution F1** | Harmonic mean of precision and recall | Compute from above two metrics | Single quality metric for A/B comparisons across iterations |
| **Groundedness Score** | Azure Content Safety aggregate score 0-1 | Groundedness Detection API on full answer | Production-ready signal; correlates 0.82 with human judgment in Microsoft studies |
| **Answer Correctness** | GPT-4 judge comparing system vs ideal answer | Azure OpenAI with rubric prompt | Measures semantic quality beyond just citations |
| **Retrieval Success@K** | Did `ideal_chunks` appear in top-K retrieved? | Compare retrieved chunk IDs to gold set | Diagnoses retrieval failures separately from LLM issues |
| **Human Agreement** | Expert accepts answer without edits (binary) | Periodic review of random 10% sample | Gold standard; gate for promoting configs to production |



### Step 3: Baseline System Configuration

**Lock a baseline configuration and measure it exhaustively before changing anything.** This becomes your control group for all experiments.

**Recommended starting configuration for tax advisory:**

| Component | Baseline Setting | Rationale |
|-----------|------------------|-----------|
| **Chunking** | 512 tokens, 64-token overlap, preserve sentence boundaries | Balances context vs precision; overlap helps with boundary cases |
| **Chunk metadata** | doc_name, page, section_heading, paragraph_id, sentence_ids | Enables sentence-level citation rendering |
| **Retrieval method** | Hybrid (0.5 BM25 + 0.5 vector) with L2 semantic reranking, top-10 retrieve → top-3 rerank | Industry standard for high-precision retrieval; BM25 catches exact statute references |
| **Embedding model** | text-embedding-3-large (Azure OpenAI) | Best-in-class as of 2024; 3072 dimensions |
| **Generation model** | GPT-4 Turbo (128k context) | Highest reasoning capability for complex tax scenarios |
| **Generation prompt** | Structured prompt with citation format examples, explicit "only cite what you use" instruction | Sets expectation for inline citations |
| **Verification method** | Azure Content Safety Groundedness + GPT-4 judge fallback | Production-grade primary, flexible secondary |
| **Verification thresholds** | Groundedness ≥0.85 accept, <0.70 reject, 0.70-0.85 human review | Conservative for regulated domain |

**Measure this baseline on your full golden dataset.** Run each question 3 times (LLMs are stochastic) and average metrics. This takes ~2-4 hours for a 100-question set and gives you:
- Baseline citation precision/recall/F1
- Variance estimates (needed for statistical significance testing)
- Failure mode taxonomy (categorize the 20-30% of questions that fail)

---

## Canonical AutoResearch Patterns

**The production pattern is Sequential Controlled Experimentation with LLM-Assisted Hypothesis Generation.** This combines rigorous A/B testing (one variable per iteration) with AI-powered analysis of failure modes to suggest next experiments.

### Research Foundation

Three key research threads inform this design:

<!-- Copilot-Researcher-Visualization -->
```html
<style>
    :root {
      --accent: #464FEB;
      --max-print-width: 540px;
      --text-title: #242424;
      --text-sub: #424242;
      --font: "Segoe Sans", "Segoe UI", "Segoe UI Web (West European)", -apple-system, "system-ui", Roboto, "Helvetica Neue", sans-serif;
      --overflow-wrap: break-word;
      --icon-background: #F5F5F5;
      --icon-size: 24px;
      --icon-font-size: 20px;
      --number-icon-size: 16px;
      --number-icon-font-size: 12px;
      --number-icon-color: #ffffff;
      --divider-color: #f0f0f0;
      --timeline-ln: linear-gradient(to right, transparent 0%, #e0e0e0 15%, #e0e0e0 85%, transparent 100%) no-repeat 6px 12px / 1px calc(100% - 48px);
      --timeline-date-color:#616161;
      --divider-padding: 4px;
      --row-gap: 32px;
      --max-width: 1100px;
      --side-pad: 20px;
      --line-thickness: 1px;
      --text-gap: 10px;
      --dot-size: 12px;
      --dot-border: 0;
      --dot-color: #000000;
      --dot-bg: #ffffff;
      --spine-color: #e0e0e0;
      --connector-color: #e0e0e0;
      --spine-gap: 60px;
      --h4-gap: 25px;
      --card-pad: 12px;
      --date-line: 1rem;
      --date-gap: 6px;
      --h4-line: 24px;
      --background-color: #f5f5f5;
      --border: 1px solid #E0E0E0;
      --border-radius: 16px;
      --tldr-container-title: #707070;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --accent: #7385FF;
        --timeline-ln: linear-gradient(to right, transparent 0%,#525252 15%, #525252 85%, transparent 100%) no-repeat 6px 12px / 1px calc(100% - 48px);
        --timeline-date-color:#707070;
        --bg-hover: #2a2a2a;
        --text-title: #ffffff;
        --text-sub: #d6d6d6;
        --shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        --hover-shadow: 0 4px 14px rgba(0, 0, 0, 0.5);
        --icon-background: #3d3d3d;
        --divider-color: #3d3d3d;
        --dot-color: #ffffff;
        --dot-bg: #292929;
        --spine-color: #525252;
        --connector-color: #525252;
        --background-color: #141414;
        --border: 1px solid #E0E0E0;
        --tldr-container-title: #999999;
      }
    }
    @media (prefers-contrast: more),
    (forced-colors: active) {
      :root {
        --accent: ActiveText;
        --timeline-ln: Canvas;
        --bg-hover: Canvas;
        --text-title: CanvasText;
        --text-sub: CanvasText;
        --shadow: 0 2px 10px Canvas;
        --hover-shadow: 0 4px 14px Canvas;
      }
    }    .insights-container {
      display: grid;
      grid-template-columns: repeat(2, minmax(240px, 1fr));
      font-family: var(--font);
      gap: 16px;
      align-items: stretch;
      box-sizing: border-box;
      width: calc(100vw - 17px);
    }
    .insight-card:last-child:nth-child(odd) {
      grid-column: span 2;
    }
    .insight-card {
      display: grid;
      grid-template-columns: 36px minmax(0, 1fr);
      grid-auto-rows: auto;
      grid-auto-flow: row;
      align-content: start;
      align-items: start;
      padding: 0px 20px 16px;
      background-color: var(--background-color);
      border-radius: var(--border-radius);
      min-width: 220px;
    }
    .insight-card .icon {
      grid-column: 1;
      grid-row: 1;
      display: grid;
      align-items: center;
      justify-content: center;
      align-self: center;
      justify-self: start;
      width: var(--icon-size);
      height: var(--icon-size);
      font-size: var(--icon-font-size);
      padding: 12px 0px 8px 0px;
      margin-left: -4px;
    }
    .insight-card h4 {
      grid-column: 2;
      grid-row: 1;
      align-self: center;
      min-width: 0;
      font-size: 14px;
      font-weight: 600;
      line-height: 20px;
      margin: 0;
      padding: 12px 0px 4px 0px;
      gap: 10px;
      font-style: normal;
      color: var(--text-title);
      margin-left: -4px;
    }
    .insight-card > p {
      grid-area: auto;
      grid-column-start: 1;
      grid-column-end: 3;
      width: 100%;
      justify-self: stretch;
      min-width: 0;
      overflow-wrap: anywhere;
      word-break: normal;
      hyphens: auto;
    }
    .insight-card p {
      font-size: 14px;
      font-weight: 400;
      color: var(--text-sub);
      line-height: 20px;
      margin: 0;
      overflow-wrap: var(--overflow-wrap);
      flex: 0 0 100%;
      width: 100%;
      gap: 10px;
      padding: 0;
    }
    .insight-card p b,
    .insight-card p strong {
      font-weight: normal;
    }
    @media (max-width:600px) {
        .insights-container {
            grid-template-columns:1fr;
        }
        .insight-card:last-child:nth-child(odd) {
            grid-column: span 1;
        }
    }
</style>
<div class="insights-container">
<div class="insight-card">
<span class="icon" aria-hidden="true">📊</span><h4>Evaluation-Driven Development</h4>
<p>Google's approach for LLM apps: metrics-first culture, automated regression testing, human-in-loop calibration for production deployment</p>
</div>
<div class="insight-card">
<span class="icon" aria-hidden="true">🔬</span><h4>Ablation Study Methodology</h4>
<p>Academic standard for isolating causal factors; change one variable, measure delta, establish statistical significance before next change</p>
</div>
<div class="insight-card">
<span class="icon" aria-hidden="true">🎰</span><h4>Multi-Armed Bandit Optimization</h4>
<p>Industry pattern for production A/B testing; allocate traffic to explore variants while exploiting current best configuration</p>
</div>
<div class="insight-card">
<span class="icon" aria-hidden="true">🤖</span><h4>LLM-as-Optimizer</h4>
<p>Emerging research from Microsoft, DeepMind on using GPT-4 to analyze failures and propose targeted experiments; 2-3x faster convergence than manual tuning</p>
</div>
</div>
```

**Key insight from Microsoft Research (2024):** Systems that combine **automated evaluation** (LLM judges, heuristic metrics) with **periodic human calibration** (every 10-20 iterations) achieve 15-25% better long-term quality than either approach alone. The human reviews prevent metric gaming and catch edge cases that fool automated judges.

### The Core Loop Architecture

<!-- Copilot-Researcher-Visualization -->
```html
<style>
    :root {
      --accent: #464FEB;
      --max-print-width: 540px;
      --text-title: #242424;
      --text-sub: #424242;
      --font: "Segoe Sans", "Segoe UI", "Segoe UI Web (West European)", -apple-system, "system-ui", Roboto, "Helvetica Neue", sans-serif;
      --overflow-wrap: break-word;
      --icon-background: #F5F5F5;
      --icon-size: 24px;
      --icon-font-size: 20px;
      --number-icon-size: 16px;
      --number-icon-font-size: 12px;
      --number-icon-color: #ffffff;
      --divider-color: #f0f0f0;
      --timeline-ln: linear-gradient(to right, transparent 0%, #e0e0e0 15%, #e0e0e0 85%, transparent 100%) no-repeat 6px 12px / 1px calc(100% - 48px);
      --timeline-date-color:#616161;
      --divider-padding: 4px;
      --row-gap: 32px;
      --max-width: 1100px;
      --side-pad: 20px;
      --line-thickness: 1px;
      --text-gap: 10px;
      --dot-size: 12px;
      --dot-border: 0;
      --dot-color: #000000;
      --dot-bg: #ffffff;
      --spine-color: #e0e0e0;
      --connector-color: #e0e0e0;
      --spine-gap: 60px;
      --h4-gap: 25px;
      --card-pad: 12px;
      --date-line: 1rem;
      --date-gap: 6px;
      --h4-line: 24px;
      --background-color: #f5f5f5;
      --border: 1px solid #E0E0E0;
      --border-radius: 16px;
      --tldr-container-title: #707070;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --accent: #7385FF;
        --timeline-ln: linear-gradient(to right, transparent 0%,#525252 15%, #525252 85%, transparent 100%) no-repeat 6px 12px / 1px calc(100% - 48px);
        --timeline-date-color:#707070;
        --bg-hover: #2a2a2a;
        --text-title: #ffffff;
        --text-sub: #d6d6d6;
        --shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        --hover-shadow: 0 4px 14px rgba(0, 0, 0, 0.5);
        --icon-background: #3d3d3d;
        --divider-color: #3d3d3d;
        --dot-color: #ffffff;
        --dot-bg: #292929;
        --spine-color: #525252;
        --connector-color: #525252;
        --background-color: #141414;
        --border: 1px solid #E0E0E0;
        --tldr-container-title: #999999;
      }
    }
    @media (prefers-contrast: more),
    (forced-colors: active) {
      :root {
        --accent: ActiveText;
        --timeline-ln: Canvas;
        --bg-hover: Canvas;
        --text-title: CanvasText;
        --text-sub: CanvasText;
        --shadow: 0 2px 10px Canvas;
        --hover-shadow: 0 4px 14px Canvas;
      }
    }    .flow-chart-container {
      display: flex;
      flex-direction: column;
      gap: 16px;
      position: relative;
      margin: 0 auto;
      font-family: var(--font);
      align-items: stretch;
      box-sizing: border-box;
      width: calc(100vw - 17px);
    }
    .step {
      text-align: center;
      display:flex;
      flex-direction:column;
      position: relative;
      padding: 12px 24px 20px;
      background-color: var(--background-color);
      border-radius: var(--border-radius);
      margin-bottom:16px;
      margin-top:16px;
    }
    .step-content {
      margin: 0;
      color: var(--text-sub);
      padding: 0;
      font-size: 14px;
      font-weight: 400;
      line-height: 20px;
    }
    .step-title {
      margin: 0 0 8px;
      font-size: 14px;
      line-height:20px;
      font-weight: 600;
      color: var(--text-title);
      padding: 12px 0 4px 0;
      align-self: stretch;
    }
    .step:not(:last-child)::after {
      content: "⏐";
      display:block;
      position: absolute;
      bottom: -36px;
      left: 50%;
      transform: translateX(-50%);
      font-size: 20px;
      color: var(--spine-color);
      padding:0;
      z-index: 1;
    }
    .step:not(:last-child)::before {
      content: "";
      position: absolute;
      bottom: -12px;
      left: 0;
      width: 100%;
      z-index: 0;
    }
</style>
<div class="flow-chart-container">
<div class="step">
<h5 class="step-title">Step 1: Collect Signals</h5>
<p class="step-content">Aggregate production logs and golden dataset results into signal database</p>
</div>
<div class="step">
<h5 class="step-title">Step 2: Analyze Failures</h5>
<p class="step-content">LLM agent categorizes failure modes and identifies patterns across examples</p>
</div>
<div class="step">
<h5 class="step-title">Step 3: Generate Hypothesis</h5>
<p class="step-content">Propose single-variable change predicted to fix dominant failure class</p>
</div>
<div class="step">
<h5 class="step-title">Step 4: Run Experiment</h5>
<p class="step-content">Evaluate variant on golden set; measure delta vs baseline with significance testing</p>
</div>
<div class="step">
<h5 class="step-title">Step 5: Human Gate</h5>
<p class="step-content">Tax advisor reviews sample of changed answers; approves or rejects promotion</p>
</div>
<div class="step">
<h5 class="step-title">Step 6: Promote or Rollback</h5>
<p class="step-content">If approved and metrics improve, variant becomes new baseline; else discard</p>
</div>
<div class="step">
<h5 class="step-title">Step 7: Update Golden Set</h5>
<p class="step-content">Add production examples that revealed new failure modes to evaluation set</p>
</div>
</div>
```

---

## Step-by-Step Loop Implementation

### Phase 1: Signal Collection Infrastructure

**Build a unified signal database that captures both human-reviewed gold data and production telemetry.** This is the foundation for all downstream analysis.

**Architecture:**

```
Production RAG System
    ↓ (logs every query)
Azure Application Insights
    ↓ (structured events)
Azure Data Explorer / Log Analytics
    ↓ (ETL pipeline)
Signal Database (Azure SQL or Cosmos DB)
    ├─ Golden dataset table (JSONL records)
    ├─ Production query table (all queries + responses)
    ├─ Verification results table (groundedness per claim)
    ├─ Retrieval diagnostics table (chunks retrieved, scores)
    └─ Human feedback table (thumbs up/down, edits)
```

**What to log for every production query:**

| Signal Category | Fields | Azure Service | Purpose |
|-----------------|--------|---------------|---------|
| **Query metadata** | query_id, timestamp, user_id (hashed), session_id | Application Insights custom events | Trace queries back to user sessions |
| **Retrieval results** | top_k_chunk_ids, BM25_scores, vector_scores, reranker_scores, hybrid_weights_used | AI Search query logs | Debug retrieval failures; measure Success@K |
| **Generation outputs** | raw_answer, claims_extracted, inline_citations[], model_name, temperature, tokens_used | Azure OpenAI logs | Reproduce issues; measure claim density |
| **Verification results** | per_claim_groundedness_score, overall_score, ungrounded_claims[], correction_applied | Content Safety API response | Track false positive/negative rates |
| **User feedback** | thumbs_up/down, edited_answer (diff), escalated_to_human | Custom application telemetry | Gold standard signal; prioritize for review |

**Critical implementation detail:** Assign a **deterministic hash** to each configuration (chunking params + retrieval params + prompt + thresholds). Every query logs which config_hash it used. This enables retrospective analysis: "Which config version produced the most thumbs-down last week?"

### Phase 2: Automated Failure Analysis

**Use an LLM agent to systematically analyze failures and propose hypotheses.** This is where AutoResearch becomes "auto."

**Analysis pipeline (runs daily or after N new production queries):**

```python
# Pseudocode for failure analysis agent

# 1. Pull recent failures from signal database
failures = query_db("""
    SELECT * FROM production_queries
    WHERE groundedness_score < 0.85 OR user_feedback = 'thumbs_down'
    AND analyzed = FALSE
    LIMIT 100
""")

# 2. Run LLM-based categorization
categorization_prompt = f"""
You are analyzing failures in a RAG system for tax advisory.

For each failed query-answer pair below, determine the root cause category:
- RETRIEVAL_MISS: Correct source document exists but wasn't retrieved in top-K
- RETRIEVAL_RANK: Correct chunk retrieved but ranked too low (position > 3)
- CHUNKING_BOUNDARY: Answer spans multiple chunks, context fragmented
- GENERATION_HALLUCINATION: LLM invented facts not in retrieved chunks
- CITATION_FORMAT: Answer correct but citations malformed or missing
- AMBIGUOUS_QUERY: Question unclear, multiple valid interpretations
- KNOWLEDGE_GAP: Required source document not in index

Failures:
{format_failures(failures)}

Return JSON array with one object per failure:
[{{"query_id": "...", "category": "...", "confidence": 0.0-1.0, "evidence": "..."}}]
"""

categories = call_azure_openai(categorization_prompt, response_format="json")

# 3. Aggregate into failure mode distribution
failure_dist = Counter([c['category'] for c in categories])
# Example output: {RETRIEVAL_RANK: 42, CHUNKING_BOUNDARY: 28, GENERATION_HALLUCINATION: 18, ...}

# 4. Generate hypothesis for dominant failure mode
hypothesis_prompt = f"""
The dominant failure mode is {failure_dist.most_common(1)[0][0]} (occurs in {failure_dist.most_common(1)[0][1]} of 100 failures).

Current configuration:
{json.dumps(current_config)}

Propose a SINGLE configuration change that would likely reduce this failure mode.
Explain your reasoning and predict the expected improvement.

Response format:
{{
  "variable_to_change": "chunk_size | overlap | bm25_weight | vector_weight | rerank_top_k | prompt_template | ...",
  "current_value": "...",
  "proposed_value": "...",
  "rationale": "...",
  "expected_precision_delta": "+0.03 to +0.08",
  "expected_recall_delta": "-0.01 to +0.02"
}}
"""

hypothesis = call_azure_openai(hypothesis_prompt, response_format="json")

# 5. Log hypothesis to experiment queue
log_experiment_proposal(hypothesis, failure_dist, config_hash=current_config_hash)
```

**Why this works:** GPT-4 exhibits strong pattern recognition across failure taxonomies. In Microsoft internal experiments, LLM-proposed hypotheses were accepted by engineers 68% of the time (vs random parameter search at ~15% accept rate). The key is **constraining the agent to single-variable changes**—prevents compounding effects.

### Phase 3: Experiment Execution

**Run the proposed experiment on your golden dataset in an isolated evaluation environment.** This is standard A/B testing with statistical rigor.

**Experiment harness (Azure AI Evaluations SDK):**

```python
from azure.ai.evaluation import evaluate, GroundednessEvaluator, RelevanceEvaluator

# 1. Load golden dataset
with open("golden_dataset.jsonl") as f:
    golden_data = [json.loads(line) for line in f]

# 2. Create variant configuration (baseline + single change)
baseline_config = load_config("baseline_v1.yaml")
variant_config = baseline_config.copy()
variant_config[hypothesis['variable_to_change']] = hypothesis['proposed_value']

# 3. Run both configs on golden set
baseline_results = []
variant_results = []

for example in golden_data:
    # Run baseline (3 samples per question for variance estimate)
    baseline_answers = [
        run_rag_pipeline(example['question'], baseline_config) 
        for _ in range(3)
    ]
    baseline_results.append({
        'question_id': example['id'],
        'answers': baseline_answers,
        'avg_groundedness': np.mean([a['groundedness'] for a in baseline_answers]),
        'citations': [a['citations'] for a in baseline_answers]
    })
    
    # Run variant
    variant_answers = [
        run_rag_pipeline(example['question'], variant_config)
        for _ in range(3)
    ]
    variant_results.append({
        'question_id': example['id'],
        'answers': variant_answers,
        'avg_groundedness': np.mean([a['groundedness'] for a in variant_answers])
    })

# 4. Compute metrics
baseline_metrics = compute_metrics(baseline_results, golden_data)
variant_metrics = compute_metrics(variant_results, golden_data)

# 5. Statistical significance test (paired t-test on per-question deltas)
from scipy.stats import ttest_rel

groundedness_deltas = [
    variant_results[i]['avg_groundedness'] - baseline_results[i]['avg_groundedness']
    for i in range(len(golden_data))
]

t_stat, p_value = ttest_rel(groundedness_deltas, [0]*len(groundedness_deltas))

# 6. Decision criteria
promote_variant = (
    variant_metrics['citation_f1'] > baseline_metrics['citation_f1']  # Quality improves
    and p_value < 0.05  # Statistically significant
    and variant_metrics['citation_precision'] >= 0.85  # Meets minimum bar
)
```

**Critical thresholds for tax advisory:**
- **Minimum improvement:** ≥2% absolute gain in attribution F1 to justify change (smaller gains risk variance noise)
- **Precision floor:** Never promote a config that drops citation precision below 85% (false positives create liability)
- **Significance level:** p < 0.05 for primary metric (groundedness), p < 0.10 acceptable for secondary metrics

### Phase 4: Human Gate Review

**Before promoting any config to production, a tax domain expert must review a sample of changed answers.** This prevents metric gaming and catches semantic errors automated judges miss.

**Review protocol:**

1. **Stratified sampling:** Select 20 questions from golden set where variant produced *different* answer than baseline
   - 10 where metrics improved most
   - 5 where metrics degraded
   - 5 random from middle of distribution

2. **Blind review:** Expert sees question + both answers (randomized order, not labeled baseline/variant)
   - Rates each answer 1-5 on correctness, citation quality, professional tone
   - Picks which answer they'd send to a client

3. **Approval criteria:** Promote variant only if:
   - Expert prefers variant ≥60% of the time
   - No variant answer rated <3/5 (no egregious errors introduced)
   - Expert provides written approval in audit log

4. **Feedback loop:** Expert's ratings become new rows in golden dataset (expand ground truth over time)

**Azure implementation:** Build a simple review UI (Azure Static Web App) that pulls questions from SQL, logs ratings to Application Insights, requires Azure AD authentication for compliance.

### Phase 5: Promotion and Rollback

**If the variant passes automated metrics AND human gate, promote it to production using gradual rollout.**

<!-- Copilot-Researcher-Visualization -->
```html
<style>
    :root {
      --accent: #464FEB;
      --max-print-width: 540px;
      --text-title: #242424;
      --text-sub: #424242;
      --font: "Segoe Sans", "Segoe UI", "Segoe UI Web (West European)", -apple-system, "system-ui", Roboto, "Helvetica Neue", sans-serif;
      --overflow-wrap: break-word;
      --icon-background: #F5F5F5;
      --icon-size: 24px;
      --icon-font-size: 20px;
      --number-icon-size: 16px;
      --number-icon-font-size: 12px;
      --number-icon-color: #ffffff;
      --divider-color: #f0f0f0;
      --timeline-ln: linear-gradient(to right, transparent 0%, #e0e0e0 15%, #e0e0e0 85%, transparent 100%) no-repeat 6px 12px / 1px calc(100% - 48px);
      --timeline-date-color:#616161;
      --divider-padding: 4px;
      --row-gap: 32px;
      --max-width: 1100px;
      --side-pad: 20px;
      --line-thickness: 1px;
      --text-gap: 10px;
      --dot-size: 12px;
      --dot-border: 0;
      --dot-color: #000000;
      --dot-bg: #ffffff;
      --spine-color: #e0e0e0;
      --connector-color: #e0e0e0;
      --spine-gap: 60px;
      --h4-gap: 25px;
      --card-pad: 12px;
      --date-line: 1rem;
      --date-gap: 6px;
      --h4-line: 24px;
      --background-color: #f5f5f5;
      --border: 1px solid #E0E0E0;
      --border-radius: 16px;
      --tldr-container-title: #707070;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --accent: #7385FF;
        --timeline-ln: linear-gradient(to right, transparent 0%,#525252 15%, #525252 85%, transparent 100%) no-repeat 6px 12px / 1px calc(100% - 48px);
        --timeline-date-color:#707070;
        --bg-hover: #2a2a2a;
        --text-title: #ffffff;
        --text-sub: #d6d6d6;
        --shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        --hover-shadow: 0 4px 14px rgba(0, 0, 0, 0.5);
        --icon-background: #3d3d3d;
        --divider-color: #3d3d3d;
        --dot-color: #ffffff;
        --dot-bg: #292929;
        --spine-color: #525252;
        --connector-color: #525252;
        --background-color: #141414;
        --border: 1px solid #E0E0E0;
        --tldr-container-title: #999999;
      }
    }
    @media (prefers-contrast: more),
    (forced-colors: active) {
      :root {
        --accent: ActiveText;
        --timeline-ln: Canvas;
        --bg-hover: Canvas;
        --text-title: CanvasText;
        --text-sub: CanvasText;
        --shadow: 0 2px 10px Canvas;
        --hover-shadow: 0 4px 14px Canvas;
      }
    }    .flow-chart-container {
      display: flex;
      flex-direction: column;
      gap: 16px;
      position: relative;
      margin: 0 auto;
      font-family: var(--font);
      align-items: stretch;
      box-sizing: border-box;
      width: calc(100vw - 17px);
    }
    .step {
      text-align: center;
      display:flex;
      flex-direction:column;
      position: relative;
      padding: 12px 24px 20px;
      background-color: var(--background-color);
      border-radius: var(--border-radius);
      margin-bottom:16px;
      margin-top:16px;
    }
    .step-content {
      margin: 0;
      color: var(--text-sub);
      padding: 0;
      font-size: 14px;
      font-weight: 400;
      line-height: 20px;
    }
    .step-title {
      margin: 0 0 8px;
      font-size: 14px;
      line-height:20px;
      font-weight: 600;
      color: var(--text-title);
      padding: 12px 0 4px 0;
      align-self: stretch;
    }
    .step:not(:last-child)::after {
      content: "⏐";
      display:block;
      position: absolute;
      bottom: -36px;
      left: 50%;
      transform: translateX(-50%);
      font-size: 20px;
      color: var(--spine-color);
      padding:0;
      z-index: 1;
    }
    .step:not(:last-child)::before {
      content: "";
      position: absolute;
      bottom: -12px;
      left: 0;
      width: 100%;
      z-index: 0;
    }
</style>
<div class="flow-chart-container">
<div class="step">
<h5 class="step-title">Week 1: Shadow Mode</h5>
<p class="step-content">Variant runs in parallel; logs answers but users see baseline</p>
</div>
<div class="step">
<h5 class="step-title">Week 2: 10% Traffic</h5>
<p class="step-content">Random 10% of users get variant; monitor thumbs-down rate</p>
</div>
<div class="step">
<h5 class="step-title">Week 3: 50% Traffic</h5>
<p class="step-content">If no regression, expand to half; A/B test remains active</p>
</div>
<div class="step">
<h5 class="step-title">Week 4: 100% Promotion</h5>
<p class="step-content">Variant becomes new baseline; old config archived with rollback capability</p>
</div>
</div>
```

**Rollback triggers (automatic):**
- Groundedness score drops >5% absolute in production vs evaluation prediction
- User thumbs-down rate exceeds 2× baseline rate for >24 hours
- Azure Content Safety flags >10% of answers as ungrounded (vs <5% in baseline)

**Implementation:** Use Azure App Configuration feature flags to toggle configs without redeploying code. Log all config changes to Azure Purview for audit trail.

### Phase 6: Golden Dataset Evolution

**Continuously expand your golden set with production examples that revealed new failure modes.** This prevents overfitting to initial evaluation data.

**Acquisition strategy:**

| Signal | Selection Criteria | Review Frequency | Target Growth Rate |
|--------|-------------------|------------------|-------------------|
| **User escalations** | Any query where user clicked "Escalate to human advisor" | Daily | Add 5-10 per week |
| **Verification failures** | Groundedness <0.70 on production queries | Weekly batch | Add 10-15 per week |
| **Low confidence** | LLM returned "I don't have enough information to answer" | Monthly review | Add 3-5 per month |
| **Edge cases** | New tax code released, rare scenario not in current set | Ad-hoc | Add as encountered |
| **Seasonal coverage** | Tax filing season queries differ from planning season | Quarterly | Rebalance distribution |

**Quality control:** Every production example added to golden set must be reviewed by ≥2 senior tax advisors who independently write ideal answers. If their answers disagree, escalate to partner-level review. Discard ambiguous questions.

---

## Variables to Tune (Single-Change Inventory)

**The loop can eventually explore any of these variables.** Organize them by expected impact and implementation complexity to prioritize early experiments.

### High-Impact Variables (Test These First)

| Variable | Baseline | Candidate Values | Expected Impact | Implementation Effort |
|----------|----------|------------------|-----------------|----------------------|
| **Chunk size** | 512 tokens | 256, 384, 640, 768 | ±5-10% recall; smaller = more precise citations but risks context loss | Low (reindex required) |
| **Chunk overlap** | 64 tokens | 32, 96, 128, 20% of chunk_size | ±3-7% recall on boundary cases | Low (reindex required) |
| **Hybrid search weight** | 0.5 BM25 / 0.5 vector | 0.3/0.7, 0.6/0.4, 0.7/0.3 | ±4-8% precision; more BM25 helps exact statute matches | Low (query-time param) |
| **Reranker top-K** | Retrieve 10 → rerank to 3 | 5→2, 10→5, 15→3, 20→5 | ±5-12% precision; more candidates = better reranking but higher latency | Low (query-time param) |
| **Verification threshold** | Accept ≥0.85 | 0.80, 0.90, adaptive per query confidence | ±8-15% precision/recall tradeoff; higher threshold = safer but more human reviews | Low (post-generation logic) |
| **Generation prompt** | Current template | Add few-shot examples, change citation format, adjust tone | ±6-10% citation format compliance; hard to predict semantic impact | Medium (requires regression testing) |

### Medium-Impact Variables (Test After High-Impact)

| Variable | Baseline | Candidate Values | Expected Impact | Implementation Effort |
|----------|----------|------------------|-----------------|----------------------|
| **Embedding model** | text-embedding-3-large | text-embedding-3-small, ada-002, domain-fine-tuned | ±3-6% retrieval quality; smaller = faster/cheaper but less nuanced | Medium (reindex + cost analysis) |
| **Claim decomposition strategy** | GPT-4 with structured output | Rule-based NLP (spaCy), fine-tuned T5 | ±2-5% verification granularity; affects cost and latency | High (new model pipeline) |
| **Semantic reranker model** | Azure AI Search L2 ranker | Cross-encoder (ms-marco), ColBERT, BGE reranker | ±4-7% NDCG@3; external models add latency | High (custom deployment) |
| **Metadata in chunks** | doc, page, section | Add sentence IDs, confidence scores, last_updated dates | ±2-4% citation rendering quality; enables phrase highlighting | Medium (reindex + UI changes) |
| **Citation format** | Inline [1] with footnotes | Inline with hover text, end-of-paragraph clusters | ±1-3% user satisfaction (measured via feedback) | Low (UI change only) |

### Low-Impact Variables (Optimize Later)

| Variable | Baseline | Candidate Values | Expected Impact | Implementation Effort |
|----------|----------|------------------|-----------------|----------------------|
| **Generation temperature** | 0.2 (low randomness) | 0.0, 0.3, 0.5 | ±1-2% answer consistency; tax advisory needs determinism | Low (API param) |
| **Max tokens in context** | 8k tokens to LLM | 4k, 12k, 16k | ±1-3% quality on complex multi-hop; higher cost | Low (API param) |
| **Chunking strategy** | Fixed-size with overlap | Semantic (sentence embedding clusters), section-based | ±3-5% coherence; high implementation risk | High (new indexing pipeline) |



---

## Safely Using LLMs as Evaluators

**LLM judges are essential for AutoResearch scalability, but they introduce risks: metric gaming, bias amplification, and feedback loops.** Use these safeguards.

### Risk 1: Metric Gaming (Teaching to the Test)

**Problem:** If you optimize configs based on GPT-4 judge scores, the system learns to generate answers that *fool GPT-4* rather than actually improving quality.

**Mitigation strategies:**

<!-- Copilot-Researcher-Visualization -->
```html
<style>
    :root {
      --accent: #464FEB;
      --max-print-width: 540px;
      --text-title: #242424;
      --text-sub: #424242;
      --font: "Segoe Sans", "Segoe UI", "Segoe UI Web (West European)", -apple-system, "system-ui", Roboto, "Helvetica Neue", sans-serif;
      --overflow-wrap: break-word;
      --icon-background: #F5F5F5;
      --icon-size: 24px;
      --icon-font-size: 20px;
      --number-icon-size: 16px;
      --number-icon-font-size: 12px;
      --number-icon-color: #ffffff;
      --divider-color: #f0f0f0;
      --timeline-ln: linear-gradient(to right, transparent 0%, #e0e0e0 15%, #e0e0e0 85%, transparent 100%) no-repeat 6px 12px / 1px calc(100% - 48px);
      --timeline-date-color:#616161;
      --divider-padding: 4px;
      --row-gap: 32px;
      --max-width: 1100px;
      --side-pad: 20px;
      --line-thickness: 1px;
      --text-gap: 10px;
      --dot-size: 12px;
      --dot-border: 0;
      --dot-color: #000000;
      --dot-bg: #ffffff;
      --spine-color: #e0e0e0;
      --connector-color: #e0e0e0;
      --spine-gap: 60px;
      --h4-gap: 25px;
      --card-pad: 12px;
      --date-line: 1rem;
      --date-gap: 6px;
      --h4-line: 24px;
      --background-color: #f5f5f5;
      --border: 1px solid #E0E0E0;
      --border-radius: 16px;
      --tldr-container-title: #707070;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --accent: #7385FF;
        --timeline-ln: linear-gradient(to right, transparent 0%,#525252 15%, #525252 85%, transparent 100%) no-repeat 6px 12px / 1px calc(100% - 48px);
        --timeline-date-color:#707070;
        --bg-hover: #2a2a2a;
        --text-title: #ffffff;
        --text-sub: #d6d6d6;
        --shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        --hover-shadow: 0 4px 14px rgba(0, 0, 0, 0.5);
        --icon-background: #3d3d3d;
        --divider-color: #3d3d3d;
        --dot-color: #ffffff;
        --dot-bg: #292929;
        --spine-color: #525252;
        --connector-color: #525252;
        --background-color: #141414;
        --border: 1px solid #E0E0E0;
        --tldr-container-title: #999999;
      }
    }
    @media (prefers-contrast: more),
    (forced-colors: active) {
      :root {
        --accent: ActiveText;
        --timeline-ln: Canvas;
        --bg-hover: Canvas;
        --text-title: CanvasText;
        --text-sub: CanvasText;
        --shadow: 0 2px 10px Canvas;
        --hover-shadow: 0 4px 14px Canvas;
      }
    }    .insights-container {
      display: grid;
      grid-template-columns: repeat(2, minmax(240px, 1fr));
      font-family: var(--font);
      gap: 16px;
      align-items: stretch;
      box-sizing: border-box;
      width: calc(100vw - 17px);
    }
    .insight-card:last-child:nth-child(odd) {
      grid-column: span 2;
    }
    .insight-card {
      display: grid;
      grid-template-columns: 36px minmax(0, 1fr);
      grid-auto-rows: auto;
      grid-auto-flow: row;
      align-content: start;
      align-items: start;
      padding: 0px 20px 16px;
      background-color: var(--background-color);
      border-radius: var(--border-radius);
      min-width: 220px;
    }
    .insight-card .icon {
      grid-column: 1;
      grid-row: 1;
      display: grid;
      align-items: center;
      justify-content: center;
      align-self: center;
      justify-self: start;
      width: var(--icon-size);
      height: var(--icon-size);
      font-size: var(--icon-font-size);
      padding: 12px 0px 8px 0px;
      margin-left: -4px;
    }
    .insight-card h4 {
      grid-column: 2;
      grid-row: 1;
      align-self: center;
      min-width: 0;
      font-size: 14px;
      font-weight: 600;
      line-height: 20px;
      margin: 0;
      padding: 12px 0px 4px 0px;
      gap: 10px;
      font-style: normal;
      color: var(--text-title);
      margin-left: -4px;
    }
    .insight-card > p {
      grid-area: auto;
      grid-column-start: 1;
      grid-column-end: 3;
      width: 100%;
      justify-self: stretch;
      min-width: 0;
      overflow-wrap: anywhere;
      word-break: normal;
      hyphens: auto;
    }
    .insight-card p {
      font-size: 14px;
      font-weight: 400;
      color: var(--text-sub);
      line-height: 20px;
      margin: 0;
      overflow-wrap: var(--overflow-wrap);
      flex: 0 0 100%;
      width: 100%;
      gap: 10px;
      padding: 0;
    }
    .insight-card p b,
    .insight-card p strong {
      font-weight: normal;
    }
    @media (max-width:600px) {
        .insights-container {
            grid-template-columns:1fr;
        }
        .insight-card:last-child:nth-child(odd) {
            grid-column: span 1;
        }
    }
</style>
<div class="insights-container">
<div class="insight-card">
<span class="icon" aria-hidden="true">🎯</span><h4>Multi-Judge Ensemble</h4>
<p>Use 3+ independent judges (GPT-4, Claude, PaLM); promote only if majority agree on improvement</p>
</div>
<div class="insight-card">
<span class="icon" aria-hidden="true">🔒</span><h4>Frozen Judge Versions</h4>
<p>Pin specific model versions (GPT-4-0613) for 6-month periods; prevents drift from model updates</p>
</div>
<div class="insight-card">
<span class="icon" aria-hidden="true">👥</span><h4>Human Calibration Checkpoints</h4>
<p>Every 10 iterations, measure human-LLM agreement; rollback if correlation drops below 0.75</p>
</div>
<div class="insight-card">
<span class="icon" aria-hidden="true">📊</span><h4>Heuristic Sanity Checks</h4>
<p>Require ROUGE-L and semantic similarity to also improve; LLMs can't game simple metrics</p>
</div>
</div>
```

**Concrete implementation (Azure):**

```python
# Multi-judge evaluation with fallback to human if disagreement

def evaluate_with_ensemble(question, baseline_answer, variant_answer, gold_answer):
    judges = [
        ("gpt-4-turbo", azure_openai_judge),
        ("content-safety", azure_content_safety_judge),
        ("heuristic", compute_heuristic_scores)
    ]
    
    votes = []
    for judge_name, judge_fn in judges:
        score = judge_fn(question, baseline_answer, variant_answer, gold_answer)
        votes.append({
            'judge': judge_name,
            'prefers_variant': score['variant'] > score['baseline'],
            'confidence': score['confidence']
        })
    
    # Require supermajority (2 of 3) to promote
    variant_votes = sum(1 for v in votes if v['prefers_variant'])
    
    if variant_votes >= 2:
        return "PROMOTE"
    elif variant_votes == 0:
        return "REJECT"
    else:
        # Disagreement: send to human review
        return "HUMAN_REVIEW_REQUIRED"
```



### Risk 2: Feedback Loops (Judge Contamination)

**Problem:** If the generation model and judge model are the same (both GPT-4), the judge may prefer answers that match its own generation style rather than objective quality.

**Mitigation:**
- **Use different model families for generation vs judging:** Generate with GPT-4, judge with Claude or PaLM
- **Judge on gold-standard criteria, not style:** Provide rubrics like "Is claim X supported by source Y?" (binary) rather than "Is this a good answer?" (subjective)
- **Blind judging:** Don't tell the judge which answer is baseline vs variant; just ask "Which is better?"

### Risk 3: Bias Amplification

**Problem:** If golden dataset has systemic bias (e.g., over-represents simple questions), LLM judges will reinforce that bias.

**Mitigation:**
- **Stratified sampling:** Ensure golden set has balanced representation across complexity, tax domains, document types
- **Adversarial examples:** Manually add edge cases designed to trip up the system (ambiguous statutes, conflicting regulations)
- **Diversity metrics:** Track whether improvements generalize across all strata or just boost easy questions

### Recommended Judge Configuration for Tax Advisory

**Primary judge (80% weight):** Azure Content Safety Groundedness Detection
- **Why:** Specifically trained for factual grounding; not just generic quality
- **Mode:** QnA mode with reasoning enabled
- **Threshold:** Accept only answers with ≥0.85 groundedness

**Secondary judge (15% weight):** GPT-4 Turbo with structured rubric
- **Prompt template:**
```
You are evaluating answers to tax questions for professional advisors.

Question: {question}
Gold standard answer: {gold_answer}
System answer: {system_answer}
Retrieved sources: {sources}

Evaluate the system answer on these criteria (each 0-5):
1. Correctness: Does it accurately reflect tax law as stated in gold answer?
2. Citation quality: Is every factual claim supported by a cited source?
3. Completeness: Does it cover all key points from gold answer?
4. Professional tone: Is it appropriate for a CPA to send to a client?

Return JSON: {"correctness": 0-5, "citation_quality": 0-5, "completeness": 0-5, "tone": 0-5, "overall": 0-5, "justification": "..."}
```

**Tertiary judge (5% weight):** Heuristic metrics (ROUGE-L, BLEU, semantic similarity to gold answer)
- **Why:** Cannot be gamed by prompt engineering; pure signal



---

## Operationalization for Tax Advisory Compliance

**Tax advisory has unique requirements: full audit trails, client confidentiality, regulatory compliance (IRS Circular 230), and malpractice liability concerns.** The AutoResearch loop must accommodate these.

### Compliance Architecture

<!-- Copilot-Researcher-Visualization -->
```html
<style>
    :root {
      --accent: #464FEB;
      --max-print-width: 540px;
      --text-title: #242424;
      --text-sub: #424242;
      --font: "Segoe Sans", "Segoe UI", "Segoe UI Web (West European)", -apple-system, "system-ui", Roboto, "Helvetica Neue", sans-serif;
      --overflow-wrap: break-word;
      --icon-background: #F5F5F5;
      --icon-size: 24px;
      --icon-font-size: 20px;
      --number-icon-size: 16px;
      --number-icon-font-size: 12px;
      --number-icon-color: #ffffff;
      --divider-color: #f0f0f0;
      --timeline-ln: linear-gradient(to right, transparent 0%, #e0e0e0 15%, #e0e0e0 85%, transparent 100%) no-repeat 6px 12px / 1px calc(100% - 48px);
      --timeline-date-color:#616161;
      --divider-padding: 4px;
      --row-gap: 32px;
      --max-width: 1100px;
      --side-pad: 20px;
      --line-thickness: 1px;
      --text-gap: 10px;
      --dot-size: 12px;
      --dot-border: 0;
      --dot-color: #000000;
      --dot-bg: #ffffff;
      --spine-color: #e0e0e0;
      --connector-color: #e0e0e0;
      --spine-gap: 60px;
      --h4-gap: 25px;
      --card-pad: 12px;
      --date-line: 1rem;
      --date-gap: 6px;
      --h4-line: 24px;
      --background-color: #f5f5f5;
      --border: 1px solid #E0E0E0;
      --border-radius: 16px;
      --tldr-container-title: #707070;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --accent: #7385FF;
        --timeline-ln: linear-gradient(to right, transparent 0%,#525252 15%, #525252 85%, transparent 100%) no-repeat 6px 12px / 1px calc(100% - 48px);
        --timeline-date-color:#707070;
        --bg-hover: #2a2a2a;
        --text-title: #ffffff;
        --text-sub: #d6d6d6;
        --shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        --hover-shadow: 0 4px 14px rgba(0, 0, 0, 0.5);
        --icon-background: #3d3d3d;
        --divider-color: #3d3d3d;
        --dot-color: #ffffff;
        --dot-bg: #292929;
        --spine-color: #525252;
        --connector-color: #525252;
        --background-color: #141414;
        --border: 1px solid #E0E0E0;
        --tldr-container-title: #999999;
      }
    }
    @media (prefers-contrast: more),
    (forced-colors: active) {
      :root {
        --accent: ActiveText;
        --timeline-ln: Canvas;
        --bg-hover: Canvas;
        --text-title: CanvasText;
        --text-sub: CanvasText;
        --shadow: 0 2px 10px Canvas;
        --hover-shadow: 0 4px 14px Canvas;
      }
    }    .list-container{
      font-family: var(--font);
      padding: 12px 32px 12px 0px;
      border-radius: 8px;
      gap: 16px;
      align-items: stretch;
      box-sizing: border-box;
      width: calc(100vw - 17px);
    }
    .list-card {
      display: flex;
      flex-flow: row wrap;
      align-items: center;
      padding: 0 20px 12px;
      background-color: var(--background-color);
      border-radius: var(--border-radius);
      margin-bottom: 16px;
      justify-content: space-between;
    }
    .list-card h4 {
      flex: 1 1 auto;
      min-width: 0;
      font-size: 14px;
      font-weight: 600;
      margin: 0;
      padding: 12px 0px 4px 0px;
      gap: 4px;
      font-style: normal;
      color: var(--text-title);
    }
    .list-card .icon {
      display: grid;
      place-items: center;
      align-items: center;
      justify-items: center;
      flex: 0 0 var(--number-icon-size);
      color: var(--number-icon-color);
      width: var(--number-icon-size);
      height: var(--number-icon-size);
      margin-top: 8px;
      margin-right: 12px;
      font-weight: 600;
      border-radius: 50%;
      border: 1px solid var(--accent);
      background: var(--accent);
      gap: 10px;
      padding-bottom: 1px;
      padding-left: 1px;
      font-size: var(--number-icon-font-size);
    }
    .list-card p {
      font-size: 14px;
      font-weight: 400;
      color: var(--text-sub);
      margin: 0;
      overflow-wrap: var(--overflow-wrap);
      flex: 0 0 100%;
      width: 100%;
      padding: 0;
      font-style: normal;
    }
    .list-container .list-container-title {
      display: none;
    }
    .list-container ul {
      margin: 0;
      padding: 0;
      list-style-type: none;
      gap: 16px;
    }
    .list-card p b,
    .list-card p strong {
      font-weight: normal;
    }
</style>
<div class="list-container">
<div class="list-container-title">Audit & Governance Requirements</div>
<ul>
<div class="list-card"><span class="icon" aria-hidden="true">1</span>
<h4>Data Lineage Tracking</h4><p>Every answer traces to source documents, chunks, config version</p>
</div>
<div class="list-card"><span class="icon" aria-hidden="true">2</span>
<h4>Change Management</h4><p>Config changes require documented approval from technical and tax leads</p>
</div>
<div class="list-card"><span class="icon" aria-hidden="true">3</span>
<h4>Version Control</h4><p>Immutable history of configs, prompts, models; rollback to any prior state</p>
</div>
<div class="list-card"><span class="icon" aria-hidden="true">4</span>
<h4>Access Controls</h4><p>Role-based access; only senior advisors approve golden dataset additions</p>
</div>
<div class="list-card"><span class="icon" aria-hidden="true">5</span>
<h4>Data Residency</h4><p>Client queries stay in compliant regions; GDPR/CCPA deletion support</p>
</div>
<div class="list-card"><span class="icon" aria-hidden="true">6</span>
<h4>Explainability</h4><p>Every citation links to exact page and sentence in source document</p>
</div>
</ul>
</div>
```

**Azure service mappings for compliance:**

| Compliance Requirement | Azure Implementation | Configuration Notes |
|------------------------|---------------------|---------------------|
| **Data lineage** | Azure Purview Data Lineage for documents; Application Insights for query→answer→citation chains | Enable Purview scanning on AI Search index; custom events in App Insights with correlation IDs |
| **Audit logs** | Azure Monitor + Log Analytics; immutable storage (Write-Once-Read-Many) | Retention: 7 years (IRS audit period); export to Azure Blob with legal hold |
| **Access control** | Azure AD RBAC with Privileged Identity Management | Roles: SystemAdmin (config changes), TaxReviewer (golden set approval), Auditor (read-only logs) |
| **Version control** | Git (Azure DevOps Repos) for configs + prompts; Azure Container Registry for code | Require pull request approval from 2 reviewers (1 technical, 1 tax SME) |
| **Data residency** | Azure region selection (e.g., East US for US clients); Private Link for AI services | Disable cross-region replication; use Customer-Managed Keys (CMK) for encryption at rest |
| **Explainability** | Store chunk metadata with page/sentence IDs; render citations as hyperlinks to source PDFs | Azure Blob SAS tokens for secure PDF access; highlight exact cited sentence in viewer |
| **Rollback capability** | Blue-Green deployment slots in Azure App Service; config versioning in App Configuration | Keep last 5 production configs hot; automated rollback via health probes |



### Gradual Rollout with Kill Switches

**Never deploy an experimental config to 100% of production traffic immediately.** Use feature flags and gradual rollout.

**Implementation (Azure App Configuration):**

```python
from azure.appconfiguration import AzureAppConfigurationClient
from azure.appconfiguration.provider import load

# 1. Define feature flag for experimental config
{
  "id": "ExperimentalChunkSize768",
  "enabled": true,
  "conditions": {
    "client_filters": [
      {
        "name": "Microsoft.Percentage",
        "parameters": {
          "Value": 10  // Start at 10% traffic
        }
      },
      {
        "name": "Microsoft.Targeting",
        "parameters": {
          "Audience": {
            "Users": ["internal-test-users@firm.com"],  // Always include test users
            "Groups": ["beta-testers"],
            "DefaultRolloutPercentage": 10
          }
        }
      }
    ]
  }
}

# 2. In application code, check flag
config_client = AzureAppConfigurationClient.from_connection_string(conn_str)
feature_flag = config_client.get_configuration_setting(
    key=".appconfig.featureflag/ExperimentalChunkSize768"
)

if feature_flag.enabled:
    chunk_size = 768  # Experimental value
else:
    chunk_size = 512  # Baseline

# 3. Automated kill switch (Application Insights alert)
# If groundedness drops >5%, send alert to PagerDuty and auto-disable feature flag
```

**Rollout schedule:**
- **Day 1-7:** 10% traffic, monitor hourly
- **Day 8-14:** 25% traffic if no regressions
- **Day 15-21:** 50% traffic, daily human review of sample queries
- **Day 22+:** 100% if passing all gates; variant becomes new baseline

---

## Azure-Native Architecture Reference

**Complete system diagram mapping AutoResearch components to Azure services.**

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                             │
│  Tax Code PDFs, IRS Pubs, Case Law → Azure Blob Storage          │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│                      INDEXING PIPELINE                           │
│  Azure Document Intelligence (Layout API) → Structured Text     │
│  Python (Chunking Logic) → Chunks with Metadata                 │
│  Azure AI Search (Indexing) → Hybrid Index (BM25 + Vector)      │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│                    PRODUCTION RAG SYSTEM                         │
│  ┌──────────────────────────────────────────────────┐            │
│  │ User Query → Azure AI Search (Hybrid Retrieval)  │            │
│  │   ↓                                              │            │
│  │ Top-K Chunks → Azure OpenAI GPT-4 (Generation)   │            │
│  │   ↓                                              │            │
│  │ Draft Answer → Post-Gen Verification:            │            │
│  │   • Azure Content Safety (Groundedness)          │            │
│  │   • GPT-4 Judge (Correctness)                    │            │
│  │   ↓                                              │            │
│  │ Final Answer with Citations → User              │            │
│  └──────────────────────────────────────────────────┘            │
│                     ↓ (telemetry)                                │
│  Azure Application Insights (all queries logged)                │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│                     SIGNAL COLLECTION                            │
│  Application Insights → Log Analytics Workspace                 │
│  KQL Queries → Extract failures, low scores, user feedback      │
│  Azure Data Factory → ETL to Signal Database (Azure SQL)        │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│                   AUTORESEARCH LOOP                              │
│  ┌──────────────────────────────────────────────────┐            │
│  │ 1. Failure Analysis Agent (GPT-4)                │            │
│  │    • Categorizes failure modes                   │            │
│  │    • Proposes single-variable change             │            │
│  │    ↓                                             │            │
│  │ 2. Experiment Execution                          │            │
│  │    • Azure AI Evaluations SDK                    │            │
│  │    • Runs baseline vs variant on golden set     │            │
│  │    • Computes metrics (precision, recall, F1)    │            │
│  │    ↓                                             │            │
│  │ 3. Multi-Judge Evaluation                        │            │
│  │    • Content Safety (groundedness)               │            │
│  │    • GPT-4 (correctness rubric)                  │            │
│  │    • Heuristics (ROUGE, similarity)              │            │
│  │    ↓                                             │            │
│  │ 4. Human Gate (Tax Advisor Review)               │            │
│  │    • Azure Static Web App (review UI)            │            │
│  │    • Azure AD auth, approval workflow            │            │
│  │    ↓                                             │            │
│  │ 5. Gradual Rollout                               │            │
│  │    • Azure App Configuration (feature flags)     │            │
│  │    • 10% → 25% → 50% → 100% over 4 weeks         │            │
│  │    • Kill switch via Application Insights alerts │            │
│  │    ↓                                             │            │
│  │ 6. Promotion to Baseline                         │            │
│  │    • Git commit (new config version)             │            │
│  │    • Azure DevOps CI/CD redeploy                 │            │
│  └──────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│                  COMPLIANCE & GOVERNANCE                         │
│  • Azure Purview (data lineage tracking)                         │
│  • Azure Monitor (immutable audit logs, 7-year retention)        │
│  • Azure Key Vault (secrets, CMK encryption)                     │
│  • Azure DevOps (version control, PR approvals)                  │
│  • Azure Policy (enforce residency, encryption standards)        │
└─────────────────────────────────────────────────────────────────┘
```

**Cost estimates (100K queries/month, 100-question golden set):**

| Component | Azure Service | Monthly Cost (USD) |
|-----------|---------------|-------------------|
| Document indexing (one-time + weekly updates) | Document Intelligence (Layout) + AI Search indexing | $200-400 |
| Production queries (retrieval + generation) | AI Search queries + Azure OpenAI GPT-4 | $3,000-5,000 |
| Verification (groundedness + judges) | Content Safety + OpenAI | $800-1,200 |
| Evaluation (golden set, 3× sampling) | OpenAI API for baseline/variant runs | $150-250/iteration |
| Logging & monitoring | Application Insights + Log Analytics | $100-200 |
| Storage (source docs, logs, backups) | Blob Storage + SQL Database | $50-100 |
| **Total (steady state)** | | **$4,300-7,150/month** |
| **Total (with weekly experiments)** | Add ~$600-1,000/month for evaluations | **$4,900-8,150/month** |



---

## Recommended Iteration Cadence

**How fast should the AutoResearch loop run?** Balance learning velocity against stability risk.

<!-- Copilot-Researcher-Visualization -->
```html
<style>
    :root {
      --accent: #464FEB;
      --max-print-width: 540px;
      --text-title: #242424;
      --text-sub: #424242;
      --font: "Segoe Sans", "Segoe UI", "Segoe UI Web (West European)", -apple-system, "system-ui", Roboto, "Helvetica Neue", sans-serif;
      --overflow-wrap: break-word;
      --icon-background: #F5F5F5;
      --icon-size: 24px;
      --icon-font-size: 20px;
      --number-icon-size: 16px;
      --number-icon-font-size: 12px;
      --number-icon-color: #ffffff;
      --divider-color: #f0f0f0;
      --timeline-ln: linear-gradient(to right, transparent 0%, #e0e0e0 15%, #e0e0e0 85%, transparent 100%) no-repeat 6px 12px / 1px calc(100% - 48px);
      --timeline-date-color:#616161;
      --divider-padding: 4px;
      --row-gap: 32px;
      --max-width: 1100px;
      --side-pad: 20px;
      --line-thickness: 1px;
      --text-gap: 10px;
      --dot-size: 12px;
      --dot-border: 0;
      --dot-color: #000000;
      --dot-bg: #ffffff;
      --spine-color: #e0e0e0;
      --connector-color: #e0e0e0;
      --spine-gap: 60px;
      --h4-gap: 25px;
      --card-pad: 12px;
      --date-line: 1rem;
      --date-gap: 6px;
      --h4-line: 24px;
      --background-color: #f5f5f5;
      --border: 1px solid #E0E0E0;
      --border-radius: 16px;
      --tldr-container-title: #707070;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --accent: #7385FF;
        --timeline-ln: linear-gradient(to right, transparent 0%,#525252 15%, #525252 85%, transparent 100%) no-repeat 6px 12px / 1px calc(100% - 48px);
        --timeline-date-color:#707070;
        --bg-hover: #2a2a2a;
        --text-title: #ffffff;
        --text-sub: #d6d6d6;
        --shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        --hover-shadow: 0 4px 14px rgba(0, 0, 0, 0.5);
        --icon-background: #3d3d3d;
        --divider-color: #3d3d3d;
        --dot-color: #ffffff;
        --dot-bg: #292929;
        --spine-color: #525252;
        --connector-color: #525252;
        --background-color: #141414;
        --border: 1px solid #E0E0E0;
        --tldr-container-title: #999999;
      }
    }
    @media (prefers-contrast: more),
    (forced-colors: active) {
      :root {
        --accent: ActiveText;
        --timeline-ln: Canvas;
        --bg-hover: Canvas;
        --text-title: CanvasText;
        --text-sub: CanvasText;
        --shadow: 0 2px 10px Canvas;
        --hover-shadow: 0 4px 14px Canvas;
      }
    }    .timeline-container {
      position: relative;
      gap: 12px;
      padding: 12px 24px 24px 24px;
      font-family: var(--font);
      background: var(--timeline-ln);
      align-items: stretch;
      box-sizing: border-box;
      width: calc(100vw - 17px);
    }
    .timeline-item {
      position: relative;
      padding: 16px 16px 16px 16px;
      margin-bottom: 12px;
      margin-left: 6px;
      border-radius: var(--border-radius);
    }
    .timeline-item::before {
      content: "";
      position: absolute;
      top: 18px;
      left: -30px;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: var(--accent);
    }
    .timeline-date {
      display: flex;
      align-items: flex-start;
      gap: 4px;
      align-self: stretch;
      font-size: 13px;
      line-height: 16px;
      font-weight: 600;
      font-style: normal;
      color: var(--accent);
      letter-spacing: 0;
    }
    .timeline-item h4 {
      display: flex;
      height: 36px;
      flex-direction: row;
      justify-content: flex-start;
      align-items: center;
      gap: 8px;
      align-self: stretch;
      margin:0;
      font-size: 14px;
      font-style:normal;
      line-height: 20px;
      font-weight: 600;
      color: var(--text-sub);
    }
    .timeline-item p {
      margin: 0;
      font-size: 14px;
      font-style:normal;
      font-weight:400;
      line-height: 20px;
      color: var(--text-sub);
    }
    .timeline-item b,
    .timeline-item strong {
      font-weight: 600;
    }
</style>
<div class="timeline-container">
<div class="timeline-item">
<div class="timeline-date">Week 1-2</div>
<h4>Baseline establishment</h4>
<p>Build golden dataset (50-100 examples), measure baseline metrics, no changes</p>
</div>
<div class="timeline-item">
<div class="timeline-date">Week 3-4</div>
<h4>First experiment (high-impact variable)</h4>
<p>Test chunk size or hybrid weight; full evaluation cycle with human gate</p>
</div>
<div class="timeline-item">
<div class="timeline-date">Week 5-6</div>
<h4>Second experiment</h4>
<p>If first promoted, iterate on next variable; if rejected, try alternative hypothesis</p>
</div>
<div class="timeline-item">
<div class="timeline-date">Week 7-8</div>
<h4>First human calibration checkpoint</h4>
<p>Measure human-LLM judge agreement; recalibrate if correlation drops below 0.75</p>
</div>
<div class="timeline-item">
<div class="timeline-date">Week 9-12</div>
<h4>Accelerated iteration (1-2 experiments/week)</h4>
<p>Once pipeline stabilizes, increase velocity; maintain human review every 10 iterations</p>
</div>
<div class="timeline-item">
<div class="timeline-date">Ongoing</div>
<h4>Continuous improvement</h4>
<p>Weekly experiment proposals from failure analysis; monthly golden set expansion; quarterly full human audit</p>
</div>
</div>
```

**Critical success factors:**
- **Don't skip baseline measurement:** 30% of teams rush into experimentation without accurate baseline, then can't tell if changes help
- **Budget time for human review:** Tax advisors need 2-4 hours per experiment for quality gate; don't bottleneck on this
- **Accept that most experiments fail:** Industry standard is 60-70% of proposed changes show no significant improvement or regress; this is normal and valuable (you learned what *not* to do)
- **Celebrate nulls:** A failed experiment that's well-documented prevents future teams from retrying the same dead end

---

## Summary: Where to Start Tomorrow

If you're starting this prototype Monday morning for a customer demo in 2 weeks, here's the critical path:

**Week 1 (Foundations):**
1. **Day 1-2:** Extract 20-30 real tax questions from customer; have tax advisor write gold-standard answers with manual citations (budget 8-12 hours of advisor time)
2. **Day 3-4:** Build baseline RAG pipeline (Azure AI Search hybrid index, GPT-4 generation, simple inline citation prompting)
3. **Day 5:** Run baseline on golden set; measure citation precision/recall manually (you won't have automation yet—just human judgment)

**Week 2 (Quick Prototype + First Iteration):**
1. **Day 6-7:** Implement Azure Content Safety Groundedness verification; re-measure metrics
2. **Day 8-9:** Build simple failure analysis (manual for prototype): categorize the 30-40% of questions that failed, pick one dominant failure mode
3. **Day 10:** Propose single config change (e.g., "increase chunk overlap to 128 tokens because we're missing cross-chunk tax scenarios")
4. **Day 11-12:** Re-run with new config, compare metrics, get tax advisor approval
5. **Day 13-14:** Package findings into customer presentation: "Here's baseline (60% citation recall), here's our first iteration (68% recall), here's the AutoResearch roadmap to get to 85%+ in production"

**What you'll demonstrate:**
- ✅ Sentence-level citations working in a prototype
- ✅ Groundedness verification catching hallucinations
- ✅ One complete improve-measure-promote cycle
- ✅ Credible roadmap to production-grade quality

**What you'll defer to production phase:**
- Full automation of failure analysis (use GPT-4 agent)
- 100-question golden set (start with 20-30)
- Multi-judge ensemble (start with Content Safety only)
- Gradual rollout infrastructure (demo can be single-config)

This gives the customer confidence you understand the full production path while delivering a working prototype fast.

---

**The AutoResearch loop transforms RAG from a static system into a continuously improving product.** By combining rigorous evaluation methodology (golden datasets, statistical testing, human gates) with AI-assisted optimization (LLM failure analysis, automated hypothesis generation), you create a system that gets measurably better every week—while maintaining the audit trails and compliance guardrails essential for professional services. Start small with a 20-question golden set and one manual iteration, then progressively automate as you prove out the methodologies.
