# Post-Generation Citation Verification Pipeline for RAG (Tax Advisory Context)

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
  <div class="tldr-card"><h3>Segment & Retrieve</h3>
    <p>Split the AI's answer into discrete factual claims and fetch matching source snippets for each.</p>
  </div>
  <div class="tldr-card"><h3>Verify & Correct</h3>
    <p>Use quick overlap checks and an LLM/NLI to confirm each claim is fully supported; rewrite or drop anything unverified.</p>
  </div>
  <div class="tldr-card"><h3>Cite & Audit</h3>
    <p>Attach precise page-level citations for supported claims and log every decision for audit and compliance.</p>
  </div>
</div>
```
[5](https://www.microsoft.com/en-us/research/blog/claimify-extracting-high-quality-claims-from-language-model-outputs/) [4](https://argonsys.com/microsoft-cloud/library/azure-cognitive-search-outperforming-vector-search-with-hybrid-retrieval-and-ranking-capabilities/) [3](https://aclanthology.org/2025.acl-industry.23/) [2](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness) [1](https://www.linkedin.com/pulse/beyond-answer-solving-page-level-citation-gap-rag-sourav-sahu-bvloc/)

**Why Verification Matters:** In enterprise settings like tax and legal advice, **producing a correct answer is not enough – every statement must be traceable to an exact source.** If an AI says “_Deduction X is allowed_,” users need to see *which page and clause* of the tax code backs that up; otherwise the AI simply creates new verification work[1](https://www.linkedin.com/pulse/beyond-answer-solving-page-level-citation-gap-rag-sourav-sahu-bvloc/). The pipeline below ensures **sentence-level groundedness** and trust by verifying each claim post-generation and providing *phrase-level citations* for validation.

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
    <span class="icon" aria-hidden="true">📑</span><h4>Traceability is Mandatory</h4>
    <p>In tax/legal advisory, answers must cite exact source pages to be trusted.</p>
  </div>
</div>
```
[1](https://www.linkedin.com/pulse/beyond-answer-solving-page-level-citation-gap-rag-sourav-sahu-bvloc/)

## High-Level Workflow Overview

1. **Claim Segmentation & Detection:** Break the LLM’s answer into individual factual statements (sentences or clauses) that can be checked independently[5](https://www.microsoft.com/en-us/research/blog/claimify-extracting-high-quality-claims-from-language-model-outputs/). Filter out or rewrite any parts that aren’t objective claims (e.g. opinions or advice) so only verifiable content remains[5](https://www.microsoft.com/en-us/research/blog/claimify-extracting-high-quality-claims-from-language-model-outputs/).  
2. **Evidence Retrieval:** For each claim, retrieve candidate supporting evidence from the knowledge base (e.g. tax codes, regulations, prior rulings). Use **hybrid keyword + vector search** with semantic re-ranking to find the most relevant passages, and preserve source metadata like document name, page, and section for precise citation[4](https://argonsys.com/microsoft-cloud/library/azure-cognitive-search-outperforming-vector-search-with-hybrid-retrieval-and-ranking-capabilities/)[1](https://www.linkedin.com/pulse/beyond-answer-solving-page-level-citation-gap-rag-sourav-sahu-bvloc/).  
3. **Heuristic Similarity Check:** Quickly assess each claim against the retrieved text using lexical overlap and embedding similarity. This step flags obvious matches or mismatches: e.g. if a claim’s key terms and semantics strongly appear in a passage. High-scoring matches are preliminarily “accepted” as likely supported, while low-scoring ones are marked for closer scrutiny[3](https://aclanthology.org/2025.acl-industry.23/).  
4. **LLM/NLI-based Verification:** Apply a stronger verification using an AI model or NLI technique. Provide each claim and its top evidence to an LLM or a specialized service to judge support: is the claim *fully supported, partially supported, or not supported* by the source? This catches subtle issues (e.g. partial truth, different figures, or contradictory info) that simple overlap might miss. Azure’s **Content Safety Groundedness API** can perform this check, flagging any ungrounded (hallucinated) content and even explaining or auto-correcting it[2](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness)[2](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness).  
5. **Answer Correction & Citation Integration:** Based on verification, adjust the answer and add citations. Fully supported claims get an inline citation pointing to the source (including exact page/section). If support is **partial or conflicting**, correct the answer: either *rewrite the statement* to align with the source (using the model’s suggestion or source data) or *omit the unsupported portion*. If no source supports a claim, drop that claim entirely. Each citation is attached at the phrase or sentence level so the user can verify every statement immediately.  
6. **Logging & Governance:** Record every step and result for auditability. Log the original question, the LLM’s draft answer, each claim’s verification status, source documents used, and the final answer with citations. This provides a compliance trail and performance metrics. It also helps monitor latency and errors: e.g. measuring added verification time and catching any recurring unsupported claims for improvement. Azure services like **Application Insights** or **Log Analytics** can capture these events, and **Purview** or similar governance tools can track data lineage (which sources contributed to which answer) for regulatory purposes.

Each step is mapped to cloud-agnostic techniques and can be implemented with **Azure-native services** as follows:

## Step 1: Claim Segmentation & Detection

**Purpose & Process:** The LLM’s answer (a free-form text) is first segmented into **discrete, verifiable claims**. We split the answer into sentences or clauses, then identify which of those are factual assertions that require support[5](https://www.microsoft.com/en-us/research/blog/claimify-extracting-high-quality-claims-from-language-model-outputs/). Any sentence that is purely opinion, advice, or generic (e.g. “**It’s important to consider X**”) is marked as **“no verifiable claim”** and excluded from citation checking[5](https://www.microsoft.com/en-us/research/blog/claimify-extracting-high-quality-claims-from-language-model-outputs/). If a sentence has both factual and non-factual parts, it can be **rewritten to isolate the factual claim** – often using an LLM to remove phrases like “this is significant because” while keeping the core fact. 

- **Implementation:** This can be done with simple rules (e.g. punctuation for splitting, keyword heuristics for factuality) or with an LLM-based tool. For high quality, one can use a method like Microsoft’s *Claimify*, which uses an LLM to extract standalone factual claims from a passage while dropping unverifiable content[5](https://www.microsoft.com/en-us/research/blog/claimify-extracting-high-quality-claims-from-language-model-outputs/)[5](https://www.microsoft.com/en-us/research/blog/claimify-extracting-high-quality-claims-from-language-model-outputs/). For example, in a tax answer containing “**This new rule likely has significant impacts on businesses**,” the system would drop the speculative phrase “likely has significant impacts” if it can’t be objectively verified. Each remaining claim should be self-contained (references like “it” or “they” clarified by context) so it can be checked without ambiguity[5](https://www.microsoft.com/en-us/research/blog/claimify-extracting-high-quality-claims-from-language-model-outputs/).

- **Inputs:** The LLM-generated answer text (from the RAG system’s initial output).  
- **Outputs:** A list of cleaned factual statements (claims). For instance: *“The 2024 tax code sets the corporate tax rate at 21%.*” Each claim is now ready for checking. Non-factual sentences are either removed or labeled to skip verification.

- **Azure Mapping:** *Azure OpenAI* can be used here to implement claim extraction logic. For example, you might prompt a GPT-4 model: *“List all factual claims in the text, excluding opinions or recommendations, and rephrase them as needed to be standalone.”* This leverages the model’s understanding to ensure no claim is missed or misphrased. Alternatively, Azure AI **Content Safety’s Groundedness detection** isn’t directly for extraction, but it could flag entire answers that have ungrounded content. In practice, an Azure Function or Logic App can orchestrate this step, and you could integrate **Azure Document Intelligence** if needed to preserve any structural context (though in this case, DI is more relevant to source documents in Step 2, as discussed next).

## Step 2: Evidence Retrieval (Hybrid Search with Metadata)

**Purpose:** For each claim, find authoritative source text that could support it. In a tax advisory scenario, sources might include IRS publications, tax law PDFs, advisory memos, etc. This step **queries a document index** to fetch passages likely to contain the information claimed, enabling phrase-level citation against original text.

**Process:** The system issues a search query for each claim. A straightforward approach is to use the claim itself (or a simplified form of it) as the query. For example, if the claim is *“The corporate tax rate is 21% as of 2024,”* the query might be _“2024 corporate tax rate 21%”_. Using a **hybrid retrieval** setup ensures maximum recall and precision: the search engine combines **keyword matching** (for exact terms like numbers or names) with **vector similarity** (for semantic matches even if wording differs)[4](https://argonsys.com/microsoft-cloud/library/azure-cognitive-search-outperforming-vector-search-with-hybrid-retrieval-and-ranking-capabilities/). Azure Cognitive Search (Azure AI Search) supports this out-of-the-box – it will perform both BM25 keyword search and vector embedding search, then merge results (Reciprocal Rank Fusion) and use a **semantic re-ranker** to push truly relevant passages to the top[4](https://argonsys.com/microsoft-cloud/library/azure-cognitive-search-outperforming-vector-search-with-hybrid-retrieval-and-ranking-capabilities/). This dramatically improves finding the correct snippet; experiments show hybrid+semantic ranking substantially outperforms vector search alone for factual queries (e.g. NDCG@3 improving from ~49 to ~63 in one benchmark)[4](https://argonsys.com/microsoft-cloud/library/azure-cognitive-search-outperforming-vector-search-with-hybrid-retrieval-and-ranking-capabilities/).

To aid **phrase-level citation**, the index should store granular metadata. We chunk documents (e.g. laws, guidelines) into reasonably small passages (e.g. paragraphs or sections ~300 tokens) *preserving natural boundaries like sentences*. During indexing, we attach **document titles, section headings, and page numbers** to each chunk. Azure’s **Document Intelligence** (Form Recognizer) can extract these from PDFs – for instance, capturing that a chunk came from “TaxCode.pdf, Page 47, Section 2.3”[1](https://www.linkedin.com/pulse/beyond-answer-solving-page-level-citation-gap-rag-sourav-sahu-bvloc/). This way, when a chunk is retrieved, we know exactly where it originated. In our example, the search might return a chunk: *“…the corporate tax rate is 21% for tax year 2024…,”* with metadata `{source: "2024_Tax_Code.pdf", page: 123}`.

For each claim, the top 1–3 passages are retrieved as **candidate evidence**. We include a short text snippet (a sentence or two) and the metadata.

- **Inputs:** A single claim (text string). The search index (comprising the domain documents, e.g. tax law corpus) is also an implicit input.  
- **Outputs:** A ranked list of candidate passages (text + metadata). e.g.: *“...the corporate tax rate is **21%** for the year 2024... (Source: 2024_Tax_Code.pdf, p.123).”* The snippet is ideally just a few sentences containing the claim’s keywords (Azure Search’s `highlight` feature can return the snippet with the query terms emphasized).

- **Azure Mapping:** Use **Azure AI Search** with both *vector* and *keyword* indexing enabled. You can enable **semantic ranking** by specifying the search mode in the query (which utilizes a Bing-trained Transformer ranker to sort the top results)[4](https://argonsys.com/microsoft-cloud/library/azure-cognitive-search-outperforming-vector-search-with-hybrid-retrieval-and-ranking-capabilities/)[4](https://argonsys.com/microsoft-cloud/library/azure-cognitive-search-outperforming-vector-search-with-hybrid-retrieval-and-ranking-capabilities/). The index is built from source documents that were processed, for example, by **Azure Document Intelligence** or an OCR pipeline to extract text and layout. Document Intelligence’s output can feed into indexing pipelines, ensuring chunk texts carry page/section info (e.g., stored in searchable fields or as annotations)[1](https://www.linkedin.com/pulse/beyond-answer-solving-page-level-citation-gap-rag-sourav-sahu-bvloc/). In practice, this means you can directly show **“[Source: Tax Code p.123]”** in the answer citation without additional lookup. If the project started from scratch (“greenfield”), embedding page numbers via DI at ingestion is the gold standard (yielding 100% accurate page citations with zero runtime cost)[1](https://www.linkedin.com/pulse/beyond-answer-solving-page-level-citation-gap-rag-sourav-sahu-bvloc/). Azure Search queries return document keys and metadata alongside text, which your app uses to form citation references.

*(If working with an existing index lacking page info, one could implement a secondary **post-retrieval mapping**: fetch the full document by ID and use a library (e.g. PyMuPDF) to locate the snippet’s page via fuzzy text match[1](https://www.linkedin.com/pulse/beyond-answer-solving-page-level-citation-gap-rag-sourav-sahu-bvloc/)[1](https://www.linkedin.com/pulse/beyond-answer-solving-page-level-citation-gap-rag-sourav-sahu-bvloc/). This adds some latency but ensures even legacy content can be cited at page-level. However, for a new prototype, it’s preferable to index with page metadata upfront.)*

## Step 3: Heuristic Similarity Verification (Quick Filter)

**Purpose:** Before invoking an expensive model for each claim, perform a **fast heuristic check** to see if the retrieved evidence likely supports the claim. This acts as a triage: if a passage obviously matches the claim, we consider it supported (and low-risk) at least provisionally; if nothing matches well, that claim is flagged as high-risk for hallucination. These checks are far less costly than a full LLM pass, so they can be done in parallel for many claims.

**Process:** For each claim–evidence pair (initially focusing on the top retrieved passage per claim):

- **Lexical overlap:** Compute how many of the claim’s significant words appear in the passage (after stripping stopwords). High overlap (especially on unique terms like names, figures, dates) is a positive signal. For example, if the claim is about “Section 179 depreciation in 2023” and the passage contains “2023” and “Section 179 expense”, that’s a good sign. Simple metrics like Jaccard similarity or term frequency can be used.  
- **Semantic similarity:** Represent the claim and passage in an embedding space and measure cosine similarity. This captures paraphrasing; e.g. claim: “allowed as a deduction” vs source: “qualifies for deduction” should yield a high cosine similarity even if wording differs. Using the same embedding model as the vector index (like `text-embedding-ada-002`) ensures consistency[4](https://argonsys.com/microsoft-cloud/library/azure-cognitive-search-outperforming-vector-search-with-hybrid-retrieval-and-ranking-capabilities/). If the cosine similarity is above a chosen threshold (say 0.8), it indicates strong semantic alignment.  

- **Threshold decision:** Define thresholds for “strong support” vs “weak support.” If a passage clears both lexical and semantic high bars (e.g. contains the key facts and has >0.85 similarity), we mark the claim **“supported (heuristic)”** and might even decide to attach that source without further changes (though we still typically do the LLM check for ultimate safety). If all retrieved passages score low (no overlap on critical words or similarity below, say, 0.6), then the claim is flagged **“unsupported (likely hallucination)”** – meaning our knowledge base doesn’t seem to contain it. Middle cases (some overlap but not a full match, or conflicting info between top passages) are marked **“ambiguous/partial”** and definitely need a deeper check.

These metrics can be tuned. For instance, the **CiteFix study** (ACL 2025) describes combining *keyword overlap and semantic similarity (via BERTScore)* as part of a post-processing step to validate citations[3](https://aclanthology.org/2025.acl-industry.23/). Their approach yielded a ~15% relative boost in overall citation accuracy with minimal latency cost[3](https://aclanthology.org/2025.acl-industry.23/), showing that simple scoring techniques can catch many mistakes without heavy computation.

- **Inputs:** Each claim + its candidate passage(s) from Step 2.  
- **Outputs:** A decision or score for each claim, e.g. a structure like: `{claim: "...", top_passage: "...", similarity_score: 0.82, tentative_status: "partial-support"}`. Additionally, you may carry forward the best passage for each claim to the next step for detailed analysis.

- **Azure Mapping:** This step is typically done in application code or a lightweight AI model:
  - Use **Azure OpenAI Embeddings** (e.g. `embedding-ada`) to encode texts and calculate cosine similarities easily via Python or an Azure Function. Azure Cognitive Search also returns a similarity score for vector matches; however, recalculating with a focused claim vs snippet embedding can be more direct for our purpose. 
  - For lexical overlap, you could use Azure Cognitive Search’s *BM25 score* as a proxy (already provided in results). Alternatively, implement a small function (possibly using Python in an Azure Function) to count keyword overlap.
  - This step is fast: calculating overlaps and dot products for, say, 10 claims × 3 passages is negligible in latency (<50ms on average). It can be parallelized across claims since each check is independent.

## Step 4: LLM-Based Fact Verification (Deep Check for Support)

**Purpose:** Now comes the **authoritative verification**. For each claim, we use an advanced model to ensure the claim is *truly* supported by the evidence, and to identify any discrepancies or unsupported details that the heuristics might miss. This step provides nuance: it can tell if support is **full, partial, or none**, and *why*. It’s effectively a fact-checking AI on top of our retrieval.

**Process:** We feed the claim and its retrieved evidence into a verification model with instructions to evaluate the relationship:
- If using a **Large Language Model (LLM)**, we prompt it with something like: *“Claim: [X]. Source: [Y]. Question: Does the source completely support the claim? Answer with: ‘Supported’, ‘Partially Supported’, or ‘Not Supported’. If partial or not, explain what is missing or different.”* A GPT-4 or GPT-3.5 model can perform this as a classification task with explanation.
- Alternatively, use a **Natural Language Inference (NLI)** approach: For example, a smaller model fine-tuned for entailment could label the claim as *entailed vs. not entailed* by the source. This yields a similar supported/unsupported judgment without a full explanation in natural language.
- **Azure Content Safety’s Groundedness Detection** offers a ready-made solution here. In **QnA mode**, you provide the model’s answer text and the set of grounding sources it *should* be based on, and the service returns which parts of the answer are *ungrounded (not found in sources)*[2](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness). It operates in two modes:
  - *Non-Reasoning mode*: a fast check that flags ungrounded content in a binary way (grounded or not)[2](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness).
  - *Reasoning mode*: a more detailed check that can highlight specific segments and provide an explanation of why something is ungrounded[2](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness). This is useful for debugging or complex cases.  

For our pipeline, we could use **non-reasoning mode for each individual claim** for speed – basically asking “is this sentence grounded in this source text?”. If it flags the sentence, we know it’s not fully supported. If it’s clean, we have high confidence the claim is supported by that source. The **reasoning mode** or an LLM with explanation can be reserved for tricky cases (e.g. partial support or conflicting info) where we need to know *what* is wrong to fix it.

**Handling Partial Support:** The verification model might find that only part of the claim is backed by the source. For example, the claim might say *“Deduction Y is allowed up to $5000 for 2024,”* but the source says $5000 with no year mentioned, or mentions 2023 instead of 2024. In such cases, we classify as **“Partially Supported”**. The model (especially if using Content Safety in reasoning mode or a GPT-4) can explicitly point out, e.g. *“Source confirms the $5000 limit but doesn’t mention 2024”*. We then know the year part is unsupported. 

**Handling Conflicting Information:** It’s possible the top two sources give different answers (though our retrieval/reranker tries to avoid showing a wrong one at top). Suppose one document says *“Deduction Y limit is $5,000”* and another (maybe outdated) says *“$3,000.”* If we provided both to the verification model, it may catch the conflict: a well-instructed LLM might respond that *sources disagree on the value*. Azure’s groundedness detector is not explicitly designed for multi-source contradiction (it focuses on answer vs sources, not source vs source), so conflict resolution may need logic in our app:
  - We might prioritize one source (e.g. the latest official regulation) and ignore the contradictory one, effectively treating the contradiction as the other source being less relevant.
  - Optionally, flag this situation for a human expert, because an AI may not have the context to decide which source is authoritative. In practice, strongly **prefer authoritative sources** in retrieval (e.g. filter or boost official documents) to minimize conflicts.

After this step, each claim is assigned a definitive status: **Supported, Partially (or Ambiguously) Supported, or Not Supported**. We also have either an explanation or signal of what’s wrong for the non-supported cases.

- **Inputs:** The claim text and one or more evidence passages. (Typically we use the top-ranked passage from Step 2 for the check. If that fails, we might try a secondary passage to see if it fares better – but in many cases if the best match didn’t support it, the others won’t either. Alternatively, multiple passages can be provided together if the claim involves several facts found in different sources.)  
- **Outputs:** A verification result for each claim, which could be a structured object, e.g.: `{claim: "...", verdict: "Supported" | "Partial" | "NotSupported" | "Conflict", details: "explanation or corrected info"}`. If using Content Safety’s API, the output may literally be the original text with certain words marked as ungrounded along with a suggested “correction” to each (for instance, it might return: *Ungrounded: "in 2024"* if the year wasn’t found, and a correction suggesting to remove or change it).

- **Azure Mapping:** There are two main Azure-centric ways to implement this:
  1. **Azure OpenAI Verification Prompt:** Deploy an *Azure OpenAI* model (e.g. GPT-4) and craft a prompt for entailment. This gives you flexibility to get nuanced answers. It’s essentially using the GPT model as an NLI engine. For example, few-shot prompting GPT-4 with examples of supported vs not supported claims can yield very accurate results. Expect each call to take perhaps ~0.5–1.5 seconds, depending on model and token sizes (the passages are short, so it’s manageable).
  2. **Azure AI Content Safety (Groundedness):** This is a turnkey solution. You call the `GroundednessDetection` API with the answer text and an array of grounding source texts[2](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness). In our case, since we verify claim by claim, you’d call it with `text = <claim>` and `groundingSources = [<passage>]`. It will return something like `{grounded: true/false, unsafe: false, ...}` plus, if using reasoning mode, an explanation or even an auto-corrected suggestion for ungrounded parts[2](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness). The *correction feature* (still in preview as of 2025) is particularly interesting: it can *rewrite the content to be grounded* based on sources[2](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness). That means if our claim was *“...in 2024”* and the source doesn’t mention 2024, the service might suggest removing the year or replacing it with the correct one from context. This can save us a manual fix.
  
  Both approaches can coexist: e.g., use Content Safety for a quick pass and GPT-4 for edge cases where a detailed analysis is needed. In terms of cloud components, these calls can be made from an Azure Function or orchestrator (like Logic Apps or Durable Functions) that manages the per-claim verification concurrently.

## Step 5: Answer Correction & Citation Integration

**Purpose:** This step takes the original answer and produces the *final, polished answer* that will be shown to the user. All corrections from the verification step are applied, and every factual claim is accompanied by a citation reference. The goal is a response that is not only correct, but also **auditably linked** to sources.

**Process:** We reconcile the results from Step 4 with the answer text:
- For each claim:
  - If **Supported**: great – we will keep this claim in the answer. Attach a citation indicator to it (like a superscript “[1]”). We’ll later map “[1]” to the source document (e.g. *“IRS 2024 Tax Code, p.123”* or a hyperlink to that page in a PDF repository). 
  - If **Partially Supported**: we need to modify the claim so that it only states what is supported. There are a few strategies:
    - **Auto-correction**: If we have a suggested correction from the Content Safety API or the LLM explanation, use that. For example, if the claim was “allowed up to $5,000 in 2024” and the model flagged “in 2024” as unsupported, we’d drop the year from the sentence (or replace it with the correct year if known). 
    - **Manual fix via code**: Sometimes the fix is straightforward (like changing a number or removing a phrase). The system can parse the explanation – e.g., if GPT-4 said “Source confirms $5,000 limit but no year given,” the code could strip the year. 
    - **Multi-source citation**: If the claim combined two facts, each from different sources, one approach is to split the claim into two sentences, each supported by one source. For instance, an answer sentence *“Deduction Y is limited to $5,000 (per IRS rules) and sunsets after 2025 (per amendment Z).”* might be split if one source confirms the $5,000 and another confirms the 2025 sunset. The final answer could present these as separate sentences with separate citations.
    - **If irreparable**: If a claim can’t be fully supported or reframed accurately (e.g. it was mostly hallucinated), it’s safer to remove it entirely. It’s better the answer be incomplete than include a potentially wrong statement with a misleading citation.
  - If **Not Supported**: this indicates a hallucination or information outside the provided sources. The action here is usually to **drop the claim**. Optionally, the system might replace it with a disclaimer: e.g., *“[Information not found in provided sources]”*, but in client-facing use it’s more common to just omit it. If the unsupported claim was critical to answering the user’s question, then the entire answer might be considered failed – but assuming our initial LLM did a decent job and we had relevant sources, this should be rare. Often it’s a minor detail that gets removed.
  - If **Conflict**: If we determined a conflict in sources and didn’t resolve it in Step 4, one approach is to **present the more authoritative info** and footnote the nuance. For example, “*Deduction Y limit is $5,000*” (with citation to official source) and perhaps add a note like “*(Another document suggests $3,000, but latest law sets $5,000.)*”. However, adding such a note is a product decision – in many cases, the system might simply choose one source to trust (preferably the official or most recent) and proceed as if the conflict weren’t there. It could log the conflict internally for an expert to review later.
- After adjusting content, assign citation numbers and assemble the references list. If multiple claims cite the same document/page, you can reuse the same reference number for them to avoid duplication. Ensure the numbering or linking is clear.

At the end of this step, we’ll have an answer where **each factual sentence ends with a citation** (or multiple citations) and there are no unchecked claims. For example, the final answer to a user’s query might look like:

> *Yes, under Section 179 of the IRS Code, equipment purchases can be deducted up to **$1,080,000** in 2022[1](https://www.linkedin.com/pulse/beyond-answer-solving-page-level-citation-gap-rag-sourav-sahu-bvloc/)[3](https://aclanthology.org/2025.acl-industry.23/). However, this deduction starts phasing out if total assets exceed $2,700,000[1](https://www.linkedin.com/pulse/beyond-answer-solving-page-level-citation-gap-rag-sourav-sahu-bvloc/).* 

*(This is an illustrative answer with dual citations per sentence: perhaps one citation is the IRS code text, and another is a trusted explainer confirming the same fact. The user can click each to verify the details.)*

**Citation format:** In an interactive app, the citations might be clickable footnote numbers or inline hyperlinks. The important part is they pinpoint the source document and ideally the exact page/section. Since our index had that metadata, we can display something like “Source: IRS Pub 946 (2022), p.5” when the user hovers or clicks.

- **Inputs:** The original answer text + the list of verification outcomes for each segmented claim + the retrieved sources for each claim (with metadata).  
- **Outputs:** The final answer text, fully revised and annotated with citations. Also a list/collection of the actual citation references (to render at the bottom of an answer or in a hover tool-tip).

- **Azure Mapping:** This step is orchestrated in application logic:
  - **Azure OpenAI** could optionally be used to regenerate the answer given instructions (e.g., “remove anything not supported and add these citations in text”), but since we have structured results from verification, it’s often reliable to handle it directly in code to avoid any new hallucination. An Azure Function can take the draft answer and a list of `{sentence, verdict, source}` and then programmatically construct the final answer.
  - The **Azure Content Safety “correction” feature** can simplify the first part: you can input the entire draft answer and the collection of sources to the API, and it will attempt to return a *corrected answer* where any ungrounded statements are replaced with grounded ones[2](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness). For example, if the draft said “the limit is $6,000” but the source says $5,000, the corrected output might have $5,000. In an ideal scenario, this could give you a nearly final answer with minimal work. In practice, you’d still want to review the changes or at least re-verify quickly that the corrections align with the source, but it’s a powerful option to consider for scale.
  - **Azure AI Search (Index)** is used again here indirectly: we use the metadata stored to format citations. For instance, we might store `documentTitle` and `pageNumber` in the index; our app can retrieve that when formatting the reference text for the user. No additional search query is needed; we already have the info from Step 2 results.
  - This is also the step to prepare the references for display. If we want to link to the actual source documents, we could use Azure Blob Storage URLs (if documents are stored there) or SharePoint links, etc., which were indexed. Azure Search can store a URL or file path with each document which our app can incorporate into the citation hyperlink.

## Step 6: Logging, Monitoring and Scaling Considerations

**Purpose:** Throughout the above pipeline, maintaining logs and monitoring performance is crucial in a professional services deployment. This final “step” runs in parallel to all others. It doesn’t transform the answer, but ensures **traceability and performance visibility** for the system maintainers and stakeholders. In regulated industries (like finance/tax advisory), you might need to demonstrate why a certain piece of advice was given, months or years later – comprehensive logs enable that.

**What to Log:** At minimum, log the **question**, the **initial LLM answer**, and the **final answer with citations**. Additionally, log intermediate details:
- Which documents were searched and which specific ones were used as sources (document IDs/names and possibly the exact passages or page numbers cited).
- Verification results per claim (e.g., which claims were altered or removed).
- Timing for each stage (to monitor latency).
- Any errors or fallbacks (e.g., if a claim had to be dropped due to no support).

These logs allow auditing: you can trace every piece of the final advice back to origin. For instance, if asked “Why did the assistant say X?”, you can check logs and see it cited *Document ABC, page 10*. You can then verify that page 10 indeed says X, proving the chain of trust.

**Governance:** Using a tool like **Azure Purview**, one could catalog all source documents and even record relationships like *“Answer to Query ID 123 was derived from Document XYZ (sections A and B)”*. This establishes data lineage, helpful for compliance. While not strictly necessary in a prototype, in production this kind of integration strengthens trust – especially if the data sources are sensitive or access-controlled.

**Monitoring Performance:** We also track metrics like how long each step takes and resource usage:
- **Latency**: Post-generation verification does add overhead, but it can be kept reasonable. Each claim verification might be, say, 200–500 ms (including search and LLM check). If an answer had 5 claims, doing them sequentially might add ~2 seconds. However, we can run them in parallel threads, keeping total added latency close to the longest single claim (~0.5s–1s). In practice, a fully verified answer might be ready in ~2–4 seconds instead of ~1–2 seconds without verification – a worthwhile trade-off for the increased confidence. (Research indicates these methods can improve citation accuracy by ~15%–20% with minimal latency impact[3](https://aclanthology.org/2025.acl-industry.23/).) We would set up alerts if this latency grows (e.g., if the LLM API is slow or if we suddenly have 50 claims to verify, which might indicate the answer is too long).
- **Scaling**: For handling many requests, the architecture should be scalable. Azure services allow scaling out:
  - Azure Cognitive Search can be scaled with more replicas/partitions to handle high query per second on retrieval.
  - Azure OpenAI can be deployed in multiple instances or scaled to higher throughput tiers; requests can be distributed to avoid bottlenecks (and you might use the cheaper fast model for verification if it’s good enough, reserving GPT-4 for generation or complex checks).
  - Steps 2–5 are good candidates for parallelization. An Azure Function workflow or Azure Durable Orchestrator can fan out the verification tasks and then fan in to collect results. This pattern ensures even if one claim takes longer, others don’t wait.
  - Caching can also help: if the same claim or query repeats, caching the search results or even verification outcome for a short period can save time. (Though in tax advisory, exact repeats are less common, but something like “what’s the 2024 rate” might get asked often – caching that answer with its citations is beneficial.)
- **Error handling**: Log any failures, e.g., if the content safety API fails or a source document can’t be retrieved. The system could have a fallback to still return the original answer (marked as unverified) rather than nothing, but with heavy logging to fix the issue.

**Azure Mapping:** 
- **Azure Monitor & Application Insights** can record custom events for each step. For example, you might log an event “ClaimVerified” with properties `claim_text`, `verdict`, `source_doc`, `latency_ms`. Similarly “AnswerFinalized” with the final answer and sources used. This data can feed into dashboards showing, say, average verification time, % of answers with dropped claims, etc.
- For governance, as noted, **Purview** could document the relationship between knowledge assets and answers. If the solution is internal, even a SharePoint or Teams message could be logged with the answer and link to sources for later review.
- **Azure Content Safety** itself provides logging of moderation events. If groundedness detection finds ungrounded content, those events could be stored (and even trigger alerts if, e.g., the LLM started hallucinating too frequently, indicating maybe the prompt or retrieval needs adjustment).
- Consider also logging the **user feedback** if available: e.g., if users can mark an answer as helpful or not, correlate that with whether our verification thought it was fully supported.

By analyzing these logs, the team can continuously improve the system (e.g., if certain types of claims often get partially supported, maybe we need more documents in the index, or adjust the prompt to avoid those claims).

---

Finally, here’s a **summary of the pipeline steps** with their roles, inputs/outputs, and Azure tooling for clarity:

| **Step**  | **Purpose** | **Key Input → Output** | **Implementation & Azure Services** |
|-----------|-------------|------------------------|-------------------------------------|
| **1. Claim Segmentation**  | Split answer into individual factual claims; drop or rewrite non-verifiable parts. | **Input:** Full LLM answer text;<br>**Output:** List of verifiable claim sentences. | Sentence tokenization (code) + optional LLM to filter/refine claims (Azure OpenAI GPT for claim extraction)[5](https://www.microsoft.com/en-us/research/blog/claimify-extracting-high-quality-claims-from-language-model-outputs/). Use Document Intelligence if needed to maintain any structure context (mostly N/A for answer text). |
| **2. Evidence Retrieval**  | Fetch supporting passages for each claim from knowledge base (ensure source metadata for citation). | **Input:** Each claim (query);<br>**Output:** Top passages with source identifiers (doc name, page, etc). | Azure AI Search index with tax/legal docs. **Hybrid search** (keyword + vector) with **semantic rerank** for high precision[4](https://argonsys.com/microsoft-cloud/library/azure-cognitive-search-outperforming-vector-search-with-hybrid-retrieval-and-ranking-capabilities/). Index populated via Azure Document Intelligence to tag page and section in each chunk[1](https://www.linkedin.com/pulse/beyond-answer-solving-page-level-citation-gap-rag-sourav-sahu-bvloc/). |
| **3. Heuristic Check**  | Quickly gauge support by comparing claim to passage text. Flag likely supported or unsupported claims. | **Input:** Claim + candidate passage;<br>**Output:** Similarity scores & preliminary support flag. | Code uses **keyword overlap** and **embedding cosine similarity** (Azure OpenAI Embeddings) to score support[3](https://aclanthology.org/2025.acl-industry.23/). Thresholds tuned from experiments (e.g., accept if >0.8 sim). Minimal latency overhead. |
| **4. LLM/Verification**  | Deep verify each claim against evidence; detect partial support or conflicts with AI reasoning. | **Input:** Claim + top evidence text(s);<br>**Output:** Verdict for each claim (“Supported”/“Partial”/“Not”) and identified issues or corrections. | **Azure OpenAI GPT-4** (prompted for entailment judgment) or **Content Safety Groundedness API** in QnA mode[2](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness). Can auto-**correct** hallucinations (Content Safety’s correction feature) for convenience[2](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness). Possibly integrate a fine-tuned NLI model for efficiency. |
| **5. Correction & Citation**  | Produce final answer with only supported claims, fixed as needed, and attach citations. | **Input:** Original answer + claim verdicts + source metadata;<br>**Output:** Final answer text with inline citations and reference list. | Python/logic to remove unsupported content and insert citation marks. Leverage **Content Safety’s corrected answer** if available to expedite fixes[2](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness). Use stored metadata (doc title, page) from Azure Search to format citations (e.g. “IRS Doc p.123”). Little to no model usage here (mostly string manipulation), ensuring determinism. |
| **6. Logging & Audit**  | Log the process and results for trust, compliance, and performance monitoring. | **Input:** All pipeline data (query, answer, sources, outcomes);<br>**Output:** Log records, audit trail entries, metrics. | **Application Insights / Log Analytics** to capture events (Azure Monitor). **Purview** for document-to-answer lineage mapping. Track latency of Azure OpenAI calls and Search queries to ensure SLA. Set up alerts for anomalies (e.g., high ungrounded rate or slow response). |

Each of these steps contributes to a scalable, **transparent RAG system**. In practice, a user of the tax advisory bot will receive an answer where every sentence is backed by a citation they can check. Behind the scenes, the system has ensured those citations are valid (using both brute-force checks and intelligent AI validation). This instills confidence: the user sees not just an answer, but an answer with proof. Moreover, if any question arises later about the advice given, the company can produce logs showing exactly which sources were relied upon – a critical factor in professional services where accountability and accuracy are paramount.


