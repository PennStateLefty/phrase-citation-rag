# AutoResearch Loop for High-Quality RAG in Tax Advisory

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
<div class="tldr-card"><h3>Start Small & Measure</h3><p>Begin with a baseline RAG pipeline (Azure Search + OpenAI) and a 100-300 question test set with correct answers & citations. Evaluate retrieval recall, answer correctness, and citation accuracy before any tuning.</p></div>
<div class="tldr-card"><h3>One Change per Iteration</h3><p>Iteratively adjust one variable at a time (chunk size, top-k, reranker, prompt wording, verification threshold). Re-run the eval set and track metrics deltas; use CI gates to prevent any metric regression.</p></div>
<div class="tldr-card"><h3>Combine Offline & Live Signals</h3><p>Use human-labeled ground truth for controlled eval and Azure Content Safety signals for production monitoring. Add new real-world failure cases to the test set each sprint to avoid overfitting.</p></div>
</div>
```
[4](https://apptension.com/guides/rag-quality-guide-evaluation-that-holds-up) [3](https://redis.io/blog/10-techniques-to-improve-rag-accuracy/) [2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework) [1](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness)

## Introduction: Why an AutoResearch Loop?

In a **regulated tax advisory** use case, quality isn’t negotiable – every answer must be correct, supported, and compliant. A Retrieval-Augmented Generation (RAG) system with **sentence-level citations** already reduces hallucinations, but maintaining its quality as you scale is challenging. Documents update, user queries evolve, and even small pipeline changes can degrade performance. An **AutoResearch loop** is a self-improving, continuous experimentation cycle (inspired by Karpathy’s pattern[5](https://www.mindstudio.ai/blog/what-is-autoresearch-loop-karpathy-business-optimization)) that systematically **tests and tunes the RAG pipeline** to keep quality high. The loop automates the classic hypothesis→experiment→result cycle:

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
    <h5 class="step-title">Step 1: Collect Data & Baseline</h5>
    <p class="step-content">Assemble ground truth Q&A+citations; run initial RAG system and measure key metrics.</p>
  </div>
  <div class="step">
    <h5 class="step-title">Step 2: Analyze & Hypothesize</h5>
    <p class="step-content">Identify top failure mode (e.g. missed document, incorrect citation) and pick one root-cause variable to adjust.</p>
  </div>
  <div class="step">
    <h5 class="step-title">Step 3: Controlled Change</h5>
    <p class="step-content">Modify that single parameter (e.g. increase top-k retrieval or tweak prompt) while keeping everything else constant.</p>
  </div>
  <div class="step">
    <h5 class="step-title">Step 4: Re-Evaluate</h5>
    <p class="step-content">Re-run the test set, compare metrics to baseline. If improved (and no other metrics tanked), promote change; else revert.</p>
  </div>
  <div class="step">
    <h5 class="step-title">Step 5: Repeat Continuously</h5>
    <p class="step-content">Log results, feed insights into next hypothesis. Over time, build a robust pipeline tuned for precision and trust.</p>
  </div>
</div>
```

This loop **automates quality improvement**. Instead of occasional big overhauls, it provides a steady, data-driven grind, always asking: *“Did this tweak make answers more accurate or citations more reliable? Prove it.”* In practice, an AutoResearch loop for RAG involves both **offline evaluations** (on a static labeled dataset) and **online monitoring** (using live system signals) to cover all bases[2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework)[2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework). Below, we detail how to set up the loop and map it to Azure services, what metrics to track, and how to avoid pitfalls like overfitting or regressions.

---

## 1. Getting Started: Minimal Viable AutoResearch Loop

**Start simple.** As Redis Labs advises, first *“baseline a naive RAG pipeline, then measure and iterate with clear metrics”*[3](https://redis.io/blog/10-techniques-to-improve-rag-accuracy/). Don’t over-engineer initial experiments – you need a stable reference point to improve upon. 

**Architectural setup:**

- **Initial RAG Pipeline (Baseline)**: For example, use **Azure AI Search** for indexing tax law documents and client memos, with hybrid retrieval (keyword + vector) enabled. Use an **Azure OpenAI** model (e.g. GPT-4) to generate answers with sources in the prompt. Keep it basic initially – few-shot examples for citing sources, moderate chunk size (e.g. 300 tokens per chunk), top-*k*=3 retrieved chunks, no fancy rerankers or verification yet. This is your control variant.

- **Ground Truth Dataset**: Assemble a **labeled QA test set** of realistically hard tax questions. Aim for a mix of easy factual lookups, complex scenario-based questions, ambiguous queries, and some unanswerable ones. **Include the expected answer and the exact supporting source snippet(s)** for each question[4](https://apptension.com/guides/rag-quality-guide-evaluation-that-holds-up). For example:
  - *Q*: “According to IRS Publication X, what’s the depreciation rate for commercial buildings?”  
    *Ground Truth*: Answer should mention 39-year straight line and cite Pub X page Y.
  - *Q*: “What’s the VAT rate in France?” (outside your docs)  
    *Ground Truth*: Mark as unanswerable, expected behavior is a refusal with no hallucination.

- **Metrics to Collect** (more details in Section 3): For each Q&A in the test set, measure:
  - **Retrieval Recall**: Did the relevant document or passage appear in the top-*k* retrieved?[2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework) 
  - **Answer Correctness**: Did the model’s answer match the ground truth facts? (Exact match or via semantic similarity)[2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework).
  - **Citation Accuracy**: Did the cited source truly support the claim? (We’ll use precision/recall for citations later.)
  - **Abstention/Refusal**: If the question had no support in corpus, did the model correctly say “I don’t know based on the provided data” instead of guessing?[4](https://apptension.com/guides/rag-quality-guide-evaluation-that-holds-up)

  Azure’s evaluation tools can help here. For instance, the **Azure AI Evaluation SDK** supports **GroundednessEvaluator**, which scores how well an answer’s statements align with the provided context[6](https://learn.microsoft.com/en-us/python/api/azure-ai-evaluation/azure.ai.evaluation.groundednessevaluator?view=azure-python). We could also use a **RetrievalEvaluator** for recall@K[7](https://learn.microsoft.com/en-us/azure/foundry-classic/how-to/develop/evaluate-sdk) and a custom evaluator for citation correctness (possibly using an NLI model or GPT-4 as a judge for each cited claim).

- **Baseline Run**: Execute the baseline pipeline on every question in the ground truth set. Log each step (query → retrieved docs → answer → citations). This gives your baseline metrics.

**Identify initial pain points:** Examine the results:
- Are many answers missing crucial info because the relevant doc wasn’t retrieved? That points to a retrieval recall issue.
- Do answers have correct facts but cite the wrong document page? That’s a citation precision problem.
- Any hallucinations (answer not supported by any doc) or erroneous refusals? That flags generation/prompt issues.

Typically, **retrieval issues are the first to tackle**: If the model never saw the right evidence, nothing else can fix the answer[2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework). Common early findings in production pilots:
- Some tax documents weren’t indexed or got chunked badly (e.g. splitting a definition across chunks[2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework)).
- The embedding model isn’t catching domain-specific terms (e.g. “§199A deduction”) – keyword search might find it, but vector search might not, or vice versa.
- The prompt might be too terse about requiring citations, so the model sometimes omits them or fabricates them.

**Choose one variable to change first**, based on the biggest observed failure mode. For example:
- If recall is low (missing docs): Increase `top_k` from 3 to 5, or enable a **hybrid search** mode to combine keyword and vector results[3](https://redis.io/blog/10-techniques-to-improve-rag-accuracy/).
- If irrelevant chunks are often retrieved: Try a smaller chunk size or overlap so each chunk is more focused (but watch out for splitting facts; keep logical units together[3](https://redis.io/blog/10-techniques-to-improve-rag-accuracy/)).
- If answers are correct but citing wrong pages: The prompt or formatting might be an issue – maybe the model isn’t strongly guided to cite *specific* supporting text. You might adjust the prompt to explicitly say “cite the page number where the info is found” or fine-tune the format.

**Implement the change in isolation.** Make sure to **hold everything else constant** – same test queries, same model, same random seed if applicable – to attribute any difference in output to this one modification[3](https://redis.io/blog/10-techniques-to-improve-rag-accuracy/).

**Re-run the evaluation** with the new setting, and compare the metrics. This leads us into the loop cycle.

---

## 2. AutoResearch Loop Design: Step-by-Step

An AutoResearch loop can be viewed as a continuous CI/CD for your RAG system’s brain. At its core, it’s about disciplined experimentation:

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
    <span class="icon" aria-hidden="true">🔄</span>
    <h4>One Variable, One Hypothesis</h4>
    <p>To attribute improvements (or regressions) to the right cause, change only <b>one parameter per experiment</b>. This scientific method approach prevents confusion over which tweak caused what effect.</p>
  </div>
  <div class="insight-card">
    <span class="icon" aria-hidden="true">📊</span>
    <h4>Metrics-Driven Decisions</h4>
    <p>Establish clear quantitative targets or at least “directional” goals. E.g., <i>“Improve citation precision by +10% without hurting answer recall”</i>. Use these to decide if a change is a success.</p>
  </div>
  <div class="insight-card">
    <span class="icon" aria-hidden="true">🤖</span>
    <h4>Automation & Logging</h4>
    <p>Automate the loop as much as possible (scheduling, reporting) and log everything (query, retrieved chunk IDs, model prompts, outputs, metrics) with a trace ID for auditing and analysis.</p>
  </div>
</div>
```
[3](https://redis.io/blog/10-techniques-to-improve-rag-accuracy/) [2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework)

Here’s the canonical loop in detail, mapped to our use case:

**Step 1: Data Collection & Baseline Evaluation** – *(We’ve covered this above.)* Maintain your **ground truth dataset** as a living object. Start with a manageable set (say 100 curated Q&As)[4](https://apptension.com/guides/rag-quality-guide-evaluation-that-holds-up). Each iteration, you might append new interesting cases (e.g. a tough query a user asked that exposed a flaw). Crucially, **partition your data** if possible: a core test set for consistent tracking of metrics, and a growing “dev” set for trying out ideas. This prevents you from accidentally overfitting to a small set of questions. 

Run the baseline pipeline and document metrics. For example, baseline might show:
- Retrieval recall@3 = 70% (30% of questions the needed doc wasn’t in the top 3 results – not great)[3](https://redis.io/blog/10-techniques-to-improve-rag-accuracy/).
- Overall answer accuracy = 60% (some answers wrong or incomplete).
- Citation precision = 50% (half of the provided citations didn’t actually support the claim).
- Groundedness (via Azure Content Safety) average score maybe 4/5 – but with 15% of answers flagged as “possible unsupported content”.
- Refusal accuracy: 2 of 5 truly unanswerable queries were correctly refused; 3 had hallucinated answers (false negatives in refusal).

These numbers illuminate where to focus.

**Step 2: Hypothesis Formation** – Based on the baseline, decide on one hypothesis for improvement. Example:
- *Hypothesis:* “Many answers are wrong because the relevant chunk wasn’t retrieved. By increasing retrieval depth from top-3 to top-5 and adding a semantic reranker, we expect recall to improve and thus answer accuracy to rise.” 
- Or: *“Citation precision is low because chunks are too large (model cites a chunk but the specific fact is elsewhere in it). By reducing chunk size from 300 to 150 tokens and overlapping by 20 tokens to avoid lost context, each citation will be more pinpoint.”*

Ground your hypothesis in evidence. If logs show that for many misses, the doc was ranked 5th or 6th, that suggests increasing *k* might help. Or if citations are off, maybe you saw the model citing an entire section when the info was in a small part of it.

**Step 3: Design the Experiment** – Plan how to test the hypothesis with a single change:
- To test retrieval changes, you might implement **Hybrid Search** in Azure AI Search (combine TF-IDF and embeddings) which research shows can *“improve end-to-end answer accuracy by ~11-15% on complex tasks”*[3](https://redis.io/blog/10-techniques-to-improve-rag-accuracy/). Or integrate an Azure Cognitive Search **Semantic Ranking** stage that re-scores top 10 results. Configure it and keep all else same.
- To test chunk size, re-index your documents with the new splitter (e.g., using Azure Cognitive Search’s built-in text split by sentence or paragraph, or pre-process with the Unstructured API for stable chunking that respects semantic boundaries[3](https://redis.io/blog/10-techniques-to-improve-rag-accuracy/)).
- If testing a prompt tweak, write the new prompt and ensure the model knows how to use it (e.g., add an example of a refusal with a citation like “[No information found – Source: None]” if you want it to explicitly indicate when it can’t answer).

Ensure you have the ability to **roll back** easily. Use source control or configuration flags for each change:
- e.g., `CHUNK_SIZE=150` in a config file or a parameter in your pipeline code.
- Use version tags for index data if re-chunking (Azure Search indexes can be duplicated or swapped).

**Step 4: Execute Experiment & Gather Metrics** – Run the same evaluation set through the new pipeline variant. Because this is automated, ideally this is a script or pipeline (could be an Azure DevOps or GitHub Actions workflow) that:
  1. Deploys the new config (or calls the updated API endpoints).
  2. Runs all test queries (could use the Azure AI Evaluation SDK to automate feeding queries and capturing responses).
  3. Computes metrics (again via SDK or your own code).
  4. Stores the results (perhaps in a CSV or database, and logs in Azure Application Insights with a run ID).

After the run, compare metrics to baseline:
- Did retrieval recall@3 (or @5 now) improve? Perhaps it went from 70% to 85%.
- Did answer accuracy go up accordingly? Maybe from 60% to 72%.
- Check citation precision/recall: if you changed chunking or prompt, did the percentage of correct citations improve (e.g. fewer mismatched citations)? 
- Critically, ensure no metric **worsened unacceptably**. Perhaps citation precision improved but recall dropped a bit, or vice versa – you need to judge trade-offs. Define **promotion criteria** clearly: e.g., “We will accept this change if answer accuracy improves by ≥5 points **and** citation precision doesn’t drop more than 2 points.”

If results are ambiguous (small differences), consider statistical significance if you have enough data. In practice with 100 queries, if you see, say, 3 more correct answers, that might be noise – you could re-run, or get more test questions to be sure.

**Step 5: Decide – Promote or Rollback** – If the experiment clearly helped, incorporate the change into the main pipeline:
- e.g. raise the top-k setting in production, or adopt the new chunking strategy (might require re-indexing content in Azure Search before next deployment).
- Also, update documentation or config as needed, and record this iteration in your change log (for governance and future reference).

If the change did **not** yield improvement, or made something worse, revert that one change:
- This is where feature flags or environment toggles shine. You can simply not merge that branch, or flip the feature flag off.
- Make a note of the outcome. Even “failed” experiments are valuable learning. For example, you might learn that “increasing top-k beyond 3 brought in too much noise, hurting precision” – good to know, and maybe the next hypothesis is to try a *smarter* retrieval method rather than just a bigger *k*.

**Loop back to Step 2** with the next hypothesis. Over time, you’ll tackle different components: retrieval, chunking, prompting, answer verification, etc. The loop runs indefinitely – it is essentially **continuous quality improvement**.

Often, teams run these loops on a **schedule**. For instance, you might do a weekly “evaluation run” of the AutoResearch loop:
- Monday: examine any new production issues or user feedback, add new test cases.
- Tuesday: form next hypothesis and implement tweak.
- Wednesday: run evaluation, analyze metrics.
- Thursday: deploy change if approved.
- Friday: monitor live stats to ensure no regression in real usage.

*(This can be accelerated or slowed as needed; Karpathy’s original AutoResearch ran nightly cycles for ML models[5](https://www.mindstudio.ai/blog/what-is-autoresearch-loop-karpathy-business-optimization), but in a high-stakes domain you might prefer a human in the loop to review changes, which could make it more weekly than daily.)*

**Automation Tip:** Use an orchestration tool to run the loop. You could script this with Python and the Azure SDKs, but for a more “agentic” approach, some have used Karpathy’s actual https://github.com/karpathy/autoresearch framework or custom logic where an agent proposes experiments. In enterprise, a simpler approach is to predefine a list of potential improvements and systematically test them. 

For example, you could queue up experiments like:
1. Increase/decrease chunk size.
2. Add bigram phrase boosting to retrieval.
3. Try GPT-4 vs GPT-3.5 for answer generation.
4. Enable Azure Content Safety’s **auto-correction** of ungrounded content (which can fix or remove unsupported sentences)[1](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness)[8](https://arxiv.org/abs/2504.15629).

Then let the loop run through these, one by one, overnight. Each morning, review a report of which change helped. There have been cases reported where this approach found an optimal setting that a human might not have tried. However, ensure oversight – automated agents might pursue a metric to the detriment of something not measured (hence next section on guardrails).

---

## 3. Metrics for Citation-Heavy RAG: What to Measure

Defining the right **quality metrics** is half the battle in an AutoResearch loop. Because we care about *grounded, correct, and trustworthy* answers, our metrics must go beyond generic accuracy. Here are the key metrics categories and how to obtain them (with a focus on citations and groundedness):

**a. Retrieval Metrics:** Affirm the system finds the needed info.
- **Recall@K**: Fraction of questions where at least one relevant document chunk is in the top-*K* retrieved[2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework). If *K*=5 yields recall 0.95, you know retrieval is covering almost all answers (but maybe overshooting with noise). Lower recall (especially if below ~0.8) means users might ask things the system *could* answer if only it fetched the right content.
- **Precision@K / MRR / NDCG**: These measure ranking quality[2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework). High recall is necessary but not sufficient; you want relevant results at rank1 because the model’s prompt has limited space. *Mean Reciprocal Rank (MRR)* or *Normalized Discounted Cumulative Gain (NDCG)* capture if the system tends to rank truly useful chunks to the top. For example, after a semantic reranker you might see NDCG@3 jump by 0.1 (which is a big improvement)[3](https://redis.io/blog/10-techniques-to-improve-rag-accuracy/).
- **Coverage of sources**: In a multi-document answer, did the system retrieve *all pieces* of needed evidence? If a question requires info from two places but retrieval only got one, the answer will be incomplete. This is a more complex metric (it’s like multi-recall), but you might label those cases in ground truth (“requires SourceA & SourceB”) and check if both were present.

*How to measure:* These metrics can be computed if you label which documents or chunk IDs are “relevant” for each query (perhaps multiple answers). Azure’s **DocumentRetrievalEvaluator** can produce recall/precision given a set of relevant document IDs for each question[7](https://learn.microsoft.com/en-us/azure/foundry-classic/how-to/develop/evaluate-sdk). Alternatively, use open tools like RAGAS or bespoke scripts.

**b. Answer Quality Metrics:** Evaluate the final answer’s content.
- **Exact Match / F1**: For questions with a well-defined answer, you can use exact match or F1-score against the ground truth answer text (commonly used in QA benchmarks). But in tax advisory, answers might be long or phrased differently, so exact match is often too strict.
- **Semantic Similarity**: a more forgiving measure: e.g., use Azure’s **QAEvaluator** or **SimilarityEvaluator**[9](https://learn.microsoft.com/en-us/python/api/azure-ai-evaluation/azure.ai.evaluation.similarityevaluator?view=azure-python) to compare the answer with the ideal answer. This yields a score (often scaled 1-5 or 0-100). High scores mean the model said basically the same thing as the ground truth.
- **Human judgment of correctness**: Ultimately, for critical domains, manual review is gold. If possible, have a tax expert verify whether the answer is correct and complete. This can be baked into the eval set creation and periodically re-checked.

However, *a crucial nuance* in RAG is that an answer can be “factually correct” yet still unacceptable if it’s **not grounded in provided sources**[10](https://mbrenndoerfer.com/writing/attribution-and-citation) (the model might have used its parametric memory). That’s why we add:

- **Groundedness/Faithfulness**: This checks that *every claim in the answer is supported by some retrieved source*. It’s essentially the inverse of hallucination rate. Azure AI Content Safety’s *groundedness detection* can evaluate this: in *“non-reasoning mode”* it quickly flags if any part of the answer likely wasn’t in the docs[1](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness). In *“reasoning mode”*, it can even highlight which sentences are ungrounded, though with more latency. Another approach is using an LLM as a judge: e.g., prompt GPT-4 with *“Does the answer contain any statements not supported by the following sources? List unsupported claims.”*. Research shows GPT-4 based judges can match human evaluators ~80% of the time in identifying ungrounded text[3](https://redis.io/blog/10-techniques-to-improve-rag-accuracy/).
  
  This can output a **groundedness score** (say 5/5 if perfectly supported, lower if some issues) – often we’d require a minimum (like 4/5) for any production-ready answer. In fact, for our loop, we might set a gate: *“No change can be promoted if it reduces the average groundedness or increases hallucination rate.”*

**c. Citation Metrics:** Since phrase-level citation is a deliverable, measure how well the system is doing at attaching sources to claims.
- **Citation Precision (per claim)**: Out of the sources the model cited, what fraction actually **support the claim** they’re attached to? Ideally 100% of citations are relevant. If the model cites an IRS code but the code section doesn’t actually mention the stated fact, that’s a precision failure. We want to drive this as high as possible (in trustworthy systems, often >90%). Low precision means the model is either citing out of habit or citing the wrong part of the doc.
  
  *Example:* Model says “... as per IRS Pub 946, Section 3, the rate is 2%【1】.” If source [1] doesn’t talk about that rate, precision is 0 for that claim.

- **Citation Recall (per claim)**: Did the model cite **all the sources** that substantiate the claim? This comes into play if multiple documents or pages contain evidence. For instance, a comprehensive answer might pull from both a tax code and a regulatory interpretation, and ideally cite both. If it only cited one, it missed some support (recall < 1). Also, if a claim was supported but the model didn’t cite anything (it happens if the model forgets to attach the reference), that’s a recall miss. High recall means the model isn’t leaving supportive evidence on the table.

- **Citation Hogging (balance)**: A softer metric – do answers over-cite (include too many references for trivial facts) or under-cite? You might count the average number of citations per answer and track trends. If after some change you see average citations dropped from 2.0 to 1.2, ensure that’s because answers got more concise, not because it started omitting needed sources.

*How to measure citations precisely?* This is tricky to fully automate, but you can leverage NLI (natural language inference) techniques:
   - For each cited source-text pair (claim vs cited passage), use an NLI model to check entailment (does the passage entail the claim?). Tools like **CiteBench** or the ALCE framework define this method. A citation is “correct” if entailment is true. With that, precision = (# entailments) / (# citations).
   - For recall, you need to know the universe of support. You could retrieve additional passages beyond what was cited and check if they also entail the claim, then see if they were cited. This is complex; often citation recall is approximated by whether at least one correct citation was provided for each claim (which would be covered by precision anyway). But if using multiple data sources, you might manually label cases where two citations were expected.

Azure’s toolkit doesn’t have a turnkey “citation precision” metric yet, but you can integrate the above logic via an **Azure OpenAI Python grader** (providing a Python code that uses an NLI model or GPT-4 in the evaluation loop)[11](https://learn.microsoft.com/en-us/python/api/azure-ai-evaluation/azure.ai.evaluation.azureopenaipythongrader?view=azure-python).

**d. Refusal/Abstention Metrics:** For a regulated scenario, answering when you don’t have support can be worse than not answering. So measure the quality of refusals:
- **Unanswerable questions answered?** – Among queries where the ground truth was “no answer” (outside scope or not in docs), did the system correctly refuse? We want no hallucinated answers. This can be measured as **Precision of Answers** – of all answered questions, what fraction should have been answered? If the system answered 100 questions and 5 should’ve been “I don’t know,” that’s 95% precision. Ideally 100%.
- **Answerable questions refused?** – Conversely, measure if the system said “no info” when in fact the answer was in the corpus. That’s an unnecessary refusal. Compute **Recall of answering** – of all answerable questions, how many were actually answered. We want that near 100% too (assuming the info is there).
- **False refusal causes** – sometimes the system fails to find info and gives up when it actually was present. This often circles back to retrieval miss or too strict verification. If you implement a verification step that sometimes wrongfully flags a correct answer as ungrounded (false positive), you’ll see an uptick in these unnecessary refusals. Track this so you can adjust verification thresholds.

These can be captured by labels in your test set and by analyzing content safety logs:
  - If using Content Safety Groundedness in production, each response gets a tag like “fully_unsupported_content” or a score. You can log when the model refuses (e.g., by checking if the response matches your refusal template). Combining these, you can see if refusals correlate to high “ungrounded” scores, and if any low-score (grounded) answers were mistakenly refused.

**Summary of Metrics & Tools:**

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
    }    .contrastive-comparison-container {
      display: grid;
      grid-template-columns: repeat(2, minmax(240px,1fr));
      gap: 16px;
      padding: 0 16px;
      margin: 0;
      font-family: var(--font);
      align-items: stretch;
      box-sizing: border-box;
      width: calc(100vw - 17px);
    }
    .contrastive-comparison-card {
      display: grid;
      grid-template-columns: 24px minmax(0, 1fr);
      grid-template-rows: minmax(24px, auto) 1fr;
      grid-template-areas:
        "icon title"
        "body body";
      column-gap: 8px;
      row-gap: 8px;
      margin: 0 0 10px;
      padding: 0 20px 16px;
      align-items: start;
      overflow: visible;
      box-sizing: border-box;
      background-color: var(--background-color);
      border-radius: var(--border-radius);
    }
    .contrastive-comparison-card .icon {
      grid-area: icon;
      width: var(--icon-font-size);
      height: var(--icon-font-size);
      font-size: var(--icon-font-size);
      align-items: center;
      justify-content: center;
      align-self: center;
      justify-self: start;
      display: inline-grid;
    }
    .contrastive-comparison-card h4 {
      grid-area: title;
      margin-bottom: 10px;
      font-weight: 600;
      line-height: 20px;
      font-size: 14px;
      align-self: center;
      align-items: center;
      color: var(--text-title);
      padding-top: 8px;
      font-style: normal;
      padding-bottom: 6px;
    }
    .contrastive-comparison-card p,
    .contrastive-comparison-card ul {
      margin: 0;
      padding-left: 4px;
      color: var(--text-sub);
      line-height: 20px;
      grid-area: body;
      min-width: 0;
      font-weight: 400;
      font-size: 14px;
      font-style: normal;
    }
    .contrastive-comparison-card ul {
      grid-area: body;
    }
    .contrastive-comparison-card li {
      display: block;
      position: relative;
      padding-left: 12px;
      margin-bottom: 8px;
    }
    .contrastive-comparison-card li::before {
      content: '';
      position: absolute;
      width: 6px;
      height: 6px;
      margin: 8px 12px 0 0;
      background-color: var(--text-sub);
      border-radius: 50%;
      left: 0;
    }
    @media (max-width:600px) {
        .contrastive-comparison-container {
            grid-template-columns:1fr;
        }
    }
</style>
<div class="contrastive-comparison-container">
  <div class="contrastive-comparison-card">
    <span class="icon" aria-hidden="true">🔍</span>
    <h4>Retrieval Metrics</h4>
    <ul>
      <li>Recall@K (coverage of evidence)</li>
      <li>Precision@K, MRR, NDCG (ranking quality)</li>
      <li>Docs needed vs retrieved (multi-source questions)</li>
    </ul>
  </div>
  <div class="contrastive-comparison-card">
    <span class="icon" aria-hidden="true">✅</span>
    <h4>Answer & Citation Metrics</h4>
    <ul>
      <li>Answer accuracy (Exact, F1, semantic sim.)</li>
      <li>Groundedness / Faithfulness</li>
      <li>Citation precision & recall</li>
      <li>Refusal correctness (no false answers)</li>
    </ul>
  </div>
</div>
```
[2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework) [6](https://learn.microsoft.com/en-us/python/api/azure-ai-evaluation/azure.ai.evaluation.groundednessevaluator?view=azure-python)  [4](https://apptension.com/guides/rag-quality-guide-evaluation-that-holds-up)

By monitoring this **basket of metrics**, you get a 360° view of quality. Often improving one metric can hurt another (classic precision/recall trade-off). For instance, making the model more cautious in citing might raise precision but lower recall (it cites only when very sure, and sometimes misses a needed citation). The AutoResearch loop helps find a good balance by iteratively searching the space of parameter options and design choices.

---

## 4. Blending Human Ground Truth with Live Signals

A robust system uses **both offline evaluation and online monitoring** in harmony[2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework)[2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework). Here’s how to leverage each without polluting the other:

**Offline (Ground Truth–Driven)**: This is your dependable yardstick. The test set doesn’t change during an experiment cycle, so improvements are measured consistently. It’s curated to cover important known scenarios (including edge cases). Use it to **make decisions** on whether a change is beneficial. Because it is small and labeled, you can use richer evaluation methods (like human review or GPT-4 judging each answer) that would be too expensive to run on every single user question.

*Avoiding contamination:* Keep the ground truth separate from any data the model trains on or sees during generation. Don’t feed these Q&A pairs into prompt templates or use them to fine-tune the model (unless you have a separate set for training). They should remain a blind test to ensure you’re measuring generalization, not just memory. If you do create a new prompt style or fine-tune the model, create new test questions or use a portion of withheld ones to validate that the improvement holds in general.

Also, be mindful of **overfitting to the test set** in your loop. If you iteratively tweak to squeeze out every last point on 100 static questions, you might end up with a system that’s specialized to that set’s peculiarities but not truly better overall. To mitigate this:
- Periodically introduce fresh questions into a secondary test set (especially if you find new failure modes). The Apptension guide suggests growing the test set every sprint to cover newly discovered issues[4](https://apptension.com/guides/rag-quality-guide-evaluation-that-holds-up).
- You can also rotate a portion of questions out and replace with new ones, to see if trends hold.

**Online (Production signals)**: This is your reality check. Users might ask crazy, unanticipated questions. The system might be used in ways you didn’t fully simulate. So set up monitoring to catch issues:
- **Content Safety / Groundedness API**: As mentioned, Azure’s service can flag ungrounded answers in real time[1](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness). In production, log these flags. For example, if in a given week 5% of answers trigger a “possible ungrounded content” alert, track that over time. If after a change it drops to 2%, great. If it jumps to 10%, you’ve potentially introduced a regression (maybe the model is taking more liberties).
- **User Feedback**: If the interface allows, collect ratings or let users report “this answer seems wrong or unsupported.” These are high-signal data points. Each such incident can be turned into a new test case for offline evaluation (with the correct answer and source labeled by a moderator) – feeding the loop new data.
- **Usage analytics**: In a customer-facing scenario, you might measure things like how often users click the provided citations (are they actually finding them useful?), or whether they ask follow-up clarification questions (maybe indicating the first answer wasn’t clear or trusted).

*Don’t mix the streams:* Use online data to **inform** your offline test design, but not as the sole measure of success. Production data is often noisy and has variable uncontrollable conditions. For example, an increase in “unsupported content” flags might be due to an influx of novel user queries rather than your last code change. That’s why you keep running the controlled offline eval in parallel – to distinguish between changes in user behavior/content and changes in your system’s logic.

A common approach is:
- **Daily Monitoring**: track key live metrics (hallucination rate, latency, maybe business KPIs like user satisfaction).
- **Triggering conditions**: If live metrics degrade beyond a threshold, it might trigger an off-cycle evaluation or even an automatic rollback if a recent deployment is the likely cause.
- **Periodic Sync**: Every couple of weeks, take a sample of real user queries (anonymize them if needed for privacy), have domain experts label them (or partially label via LLM+human validation), and merge them into the eval set. This ensures the evaluation evolves with the domain and the users, without directly fitting on the production data.

**Azure tie-in:** Azure Application Insights can be your friend here. You can create custom events/metrics for things like “AnswerHallucinationFlag=True” or “AnswerSourcesClicked=2” and use Application Insights or Log Analytics to watch these over time. If you use **Azure Monitor**, set up alerts for anomaly detection (e.g., sudden spike in ungrounded answers) to catch silent quality decay.

Azure Purview (now part of Microsoft Purview governance) can track data lineage – in a complex org, you could use it to ensure that the documents used for answers are properly catalogued and access-controlled. For example, Purview could log that an answer about “Tax Rule 123” was derived from Document ID XYZ in the corp repository, which is a regulatory filing from 2021, thus providing an audit trail of data provenance. This isn’t part of the loop per se, but it’s a **governance requirement** often in regulated industries: you need to show which sources contributed to advice given to a client.

---

## 5. Guardrails: Ensuring Reliable Progress

An AutoResearch loop must be kept on track; otherwise, it can “optimize” itself in unwanted ways. Here are some safeguards:

- **Establish Regression Gates:** Before applying any change broadly, enforce that it passes certain gates. For instance, require that on the test set, *all critical metrics stay within tolerated ranges*. The Unstructured framework suggests tying each gate to a specific failure mode (e.g. a drop in faithfulness or an increase in unanswered questions) and automating these checks in CI[2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework). If a change fails a gate, it doesn’t get deployed. This is like unit tests for your model’s quality. 

  > **Example:** *Gate 1:* Groundedness cannot drop by more than 0.1 points.  
  > *Gate 2:* If any known sensitive query (e.g. “tax fraud scenario”) that previously had a correct refusal now gets an answer, block the release.

  This prevents well-meaning changes from sneaking in new problems. It’s important to not have too many gates (to avoid analysis paralysis) – focus on the handful of metrics that matter most to your use case[2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework) (likely grounded accuracy and citation fidelity for us).

- **Monitor in Production (Canary Releases):** When possible, do a phased rollout. For instance, deploy the new model or setting to 10% of sessions (or an internal pilot group of users) and watch live metrics closely. If everything looks good, scale up to 100%. If there’s a dip in live quality signals, you can roll back quickly. Azure’s deployment slots and the Azure OpenAI *“staging”* and *“production”* endpoints can facilitate this for model changes.

- **Human Oversight for Critical Changes:** Some loop iterations will involve major shifts – e.g., switching the LLM or enabling an automated citation post-processor. Those shouldn’t be fully hands-off. Plan for a human (or a review board) to sign off on big moves. Use the loop’s findings as evidence in those discussions. For example, if GPT-4 is performing 15% better but costs 10x more than GPT-3.5, the decision might involve business stakeholders weighing accuracy vs cost. The loop provides the data (15% accuracy gain on test set[8](https://arxiv.org/abs/2504.15629); estimated cost impact, etc.), but leadership makes the call.

- **Preventing Overfitting to Eval Set:** We touched on this, but to reiterate: regularly refresh the test set with new questions and scenarios. If you find yourself coding special-case logic that only improves things for one or two test queries, step back – are you generalizing or just hacking to the test? One anti-pattern would be prompt engineering to handle a very specific phrasing that appeared in the eval set but rarely occurs in real questions. Avoid chasing metrics blindly; ensure improvements correspond to real-world value. Keep a portion of the test set as a **hold-out** (not looked at until a final evaluation) to sanity-check that your improvements are real. This is akin to having a validation vs. test split in ML.

- **Watch for Silent Decay:** Quality might degrade slowly due to factors outside your immediate control – e.g., the document corpus changes (new tax law with language the model is unfamiliar with), or the user base shifts to asking new kinds of questions. To catch these:
  - Keep an eye on long-term trends in metrics both offline and online. If you see a slow downward drift in say, groundedness, investigate. Maybe the model needs an update or the retrieval needs re-tuning for new content.
  - Use the loop to test the current system against older versions periodically. For instance, once a month, run the old baseline model (if still available) on the current test set and compare to the current model’s performance. If the old simpler model is now outperforming the new one on some metrics, you may have regressed through cumulative small changes. This is akin to having a fixed “champion” model to beat with each new candidate (common in ML model management).
  - Utilize the **audit logs**. Because you logged every experiment’s results and every production deployment’s metrics, you can trace back when a metric started falling. For example, *“We see citation precision started dropping in October – oh, that’s when we enabled the new summarizer; perhaps it’s over-summarizing away the specific details needed for citations.”* That insight can drive a new loop iteration or a rollback of that feature.

- **Document All Changes & Assumptions:** In a regulated environment, you want an audit trail of your improvements. Keep a record (even just a Wiki or markdown file in your repo) of each experiment: what was changed, why, and the results. This helps for compliance (proving you systematically improved the system and tested it) and for onboarding new team members into why the system is configured as it is. Microsoft’s guidance notes that in regulated settings, the evaluation records become part of how you govern the model’s behavior[2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework).

**Avoid metric myopia:** While we focus on factual accuracy and citations, don’t forget other aspects of quality – e.g., **response time** (users won’t wait 30 seconds for a perfect answer), **readability** (an answer that is 100% cited but utterly convoluted is not desirable), and **safety** (ensure the loop doesn’t degrade the model’s compliance with harmful content policies while chasing factuality). Thus, include some non-negotiable checks in each iteration:
- The answer should not become excessively long or slow. Set a latency budget (say <5s per query 95th percentile).
- Check a few sample outputs manually to ensure they still sound like helpful prose and not just a patchwork of quotes.
- Always run the standard AI safety filters (Azure OpenAI has them built-in). If an iteration accidentally caused the model to output something non-compliant (maybe a prompt change removed an important instruction), catch that in testing. 

In summary, guardrails ensure your AutoResearch loop optimizes what you **intend** to optimize (user-valued metrics) and doesn’t degrade or tunnel-vision on one number. As the Redis article put it, RAG development should treat the benchmark like a product artifact under change control[3](https://redis.io/blog/10-techniques-to-improve-rag-accuracy/) – meaning you handle your evaluation and quality criteria with the same rigor as production code. 

---

## 6. Scaling from Prototype to Production

Finally, consider how this continuous improvement loop itself scales and fits into the enterprise context:

**Cost Management:** Each experiment might incur significant compute cost (running a GPT-4 model on 200 queries isn’t cheap, nor is re-indexing large document sets frequently).
- Use cheaper proxies when you can. For retrieval tests, you don’t always need the full LLM; you can measure recall with just the search component. For citation evaluation, consider using a smaller NLI model (like DeBERTa or MiniLM) for initial scoring, reserving GPT-4 verification for borderline cases – this was the approach in the CiteFix research, where lightweight methods handled most checks and the expensive model was a last resort[8](https://arxiv.org/abs/2504.15629).
- Leverage caching. If you re-run similar evals many times, cache intermediate results. For instance, embed your test questions once and reuse those embeddings for retrieval experiments, rather than re-embedding each run. If using OpenAI API, ensure you’re not re-generating ground truth answers with the model (you have them labeled).
- Monitor cost alongside quality. Treat cost per query as a metric to optimize too. Perhaps you introduce a more complex verification that improves accuracy but doubles latency and cost; you might later experiment with a cheaper verification model to save money. The loop can include cost-per-query as a metric to keep an eye on (making sure it stays within a threshold).
- Azure angle: Use **Azure Cost Management** to tag evaluation runs and experiments. Also, some Azure services have pricing tiers that allow a certain number of free operations (e.g., Cognitive Search vector queries or Content Safety calls in moderate volume). Use those in staging where possible.

**Latency and Throughput:** As you add steps (rerankers, verification, etc.), the pipeline may slow down. Continuously measure end-to-end latency in your evals as well. Set a performance budget. For example, if baseline was 2.5 seconds per query and a new change makes it 5 seconds, that might be too slow for interactive use. You may decide to only deploy changes that keep latency under, say, 4 seconds P95. Strategies to maintain performance at scale:
- Do heavy processing in parallel. For instance, you can parallelize retrieval and verification calls using async patterns or Azure Functions. If the loop finds a beneficial but slow approach (like running two different LLMs), consider if you can run them concurrently.
- Use scaling infrastructure: If you deploy the RAG as an Azure Web App or Function, ensure it scales out (multiple instances) to handle load, especially if the loop made the single-query work heavier.
- Profiling: The loop can reveal which part of the pipeline is the bottleneck after changes. Perhaps after adding hybrid retrieval + rerank + verification, the new bottleneck is actually network overhead. That might spawn a non-quality optimization like caching frequent queries or tuning the Azure Search tier.

**Governance & Compliance:** In tax advisory, any AI solution likely faces compliance review. The AutoResearch loop’s outputs (evaluation reports, logs of model decisions) can feed into governance:
- **Azure Purview** (now unified under Microsoft Purview) can maintain a catalog of data sources and their usage. After each experiment, you might update documentation on which data is being used and ensure it’s properly labeled (especially if new documents are added to the index).
- **Version control for models and prompts:** Treat a prompt template or chain configuration as a versioned artifact. You can store these in a repository and tag them when deploying. The loop’s iterative nature means you might have dozens of prompt variants tested over months – keep the ones that were successful and note why others were not.
- **Audit trails:** Because you log each answer with its citations and a trace ID[2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework), you have the ability to later show *why* a particular answer was given (“it cited these sources, and here’s the chain-of-thought or verification log”). This is critical for defending the system’s decisions in audits or client questions.

**Example Mapping to Azure Services:**

- **Azure DevOps Pipelines/GitHub Actions**: Automate the loop, running evaluation scripts and storing artifacts (could output a results report).
- **Azure AI Search**: Host multiple indexes or use synonyms/semantic config variations to test retrieval hypotheses (you can script creating a new index with different analyzers or chunking).
- **Azure OpenAI**: Host multiple deployments (one for GPT-4, one for GPT-35) to A/B test model choices conveniently.
- **Azure Application Insights**: Ingest custom events from both eval runs and production. You could send an event like `EvaluationRunCompleted` with properties: commit ID, metrics, etc. Also log `ProductionAnswer` events with flags for groundedness, etc. Use KQL queries to compare runs or detect anomalies.
- **Azure AI Content Safety**: Use the Groundedness detection in production to get real-time feedback on supportiveness[1](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness) – particularly valuable for compliance to ensure no unsupported claims slip by. For example, integrate it so that if it finds an answer “not grounded,” you log that and you might even auto-regenerate the answer with a stricter prompt (some systems do a second-pass: if first answer ungrounded, they ask the model to try again but only use provided data).

**Enterprise scaling**: As the loop proves its worth in one use case, it can be extended. Perhaps the tax advisory solution expands to also cover legal or accounting domains – each with their own document sets and quirks. The AutoResearch methodology applies similarly: establish domain-specific test sets and iterate. But be careful about scope creep – ensure the loop for tax stays focused; don’t mix metrics from unrelated domains in one pot.

**Security**: In production, ensure that the loop’s automation (which might involve running model queries automatically) doesn’t inadvertently expose sensitive data. Use test questions that are safe to run through the model (no proprietary client data unless in a secure environment). Also, if using any production logs as input for new tests, anonymize them.

By scaling gradually – first proving on a small scale that each improvement helps – you avoid the Big Bang rewrite trap. The loop gives a controlled path from prototype to robust system. It’s akin to continuous integration testing: every small change is validated. This reduces risk when deploying an AI system in a field where mistakes can have serious consequences.

---

## Conclusion: A Practical, Evolving Blueprint

Implementing an AutoResearch loop for a RAG system with rich citations and verification is an investment in **continuous quality assurance**. It aligns with the principle that *“if you cannot measure it, you cannot improve it”*. By methodically measuring and tuning:

- We **improve trust** in the AI’s answers (each iteration should reduce unsupported statements and increase correct attributions),
- We **adapt to change** – as tax laws update or user behavior shifts, the loop incorporates those into the evals and suggests adjustments,
- We **document progress** – every enhancement is evidence-backed, which is invaluable for stakeholder buy-in and compliance audits.

Remember that the loop is not fully “fire-and-forget.” Especially early on, it will require careful steering. But over time, you’ll find that many improvements become routine (e.g. adjusting to a new data source might just mean adding it and letting the evaluation confirm retrieval recall remains high).

In the end, this approach turns model refinement into a **scientific process** rather than guesswork. Rather than “we hope the new prompt is better,” you’ll say “the new prompt increased answer groundedness by 8% and users clicked 20% more citations – let’s ship it”[3](https://redis.io/blog/10-techniques-to-improve-rag-accuracy/)[2](https://unstructured.io/insights/rag-evaluation-a-data-pipeline-performance-framework). For a professional services firm leveraging AI, that level of rigor is key to delivering reliable, transparent advice at scale.

**Next steps:** set up your initial test set and automation pipeline. Run a baseline to get your starting metrics. That first data point will illuminate the clearest next step (maybe it’s retrieval, maybe the model needs to be bigger). From there, the AutoResearch loop will guide you, one evidence-backed step at a time, toward a high-quality, trustworthy RAG solution for tax advisory.


