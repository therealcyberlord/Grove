---
name: deep-dive-analysis
description: Full multi-dimensional analysis of a single stock using all three research subagents. Use when the user asks for a full analysis, deep dive, comprehensive overview, or complete investment thesis on a single stock.
---

# Deep Dive Analysis

## Procedure

1. Call all three subagents in parallel:
   - news_macro - sentiment, events, macro context
   - market_data - valuation and financial metrics
   - filings - qualitative 10-K analysis
3. Synthesize all three responses into the output format below.

For the filings task, also include form type "10-K" in the description.

## Synthesis

1. Write the executive summary last, after reviewing all findings. Cover: overall verdict (bullish / bearish / neutral), the single most important financial finding, the primary risk, and one forward-looking point. 4-5 sentences maximum.
2. Include the Financials section from market_data exactly as returned. Where other subagents give context for a metric (a news event explains an elevated P/E, a filing reveals margin pressure), add a brief inline note - do not alter the numbers.
3. Reconcile conflicting signals explicitly. If news sentiment is bearish but financials are strong, name the tension and explain which signal is more forward-looking.
4. End with an Investment Thesis identifying the single key catalyst and the single key risk.
5. Deduplicate all source URLs in a consolidated Sources section.

Cite Yahoo Finance data as "Source: Yahoo Finance".

## Output format

## {TICKER} - Research Report

### Executive Summary
[4-5 sentences: verdict, financial highlight, primary risk, forward outlook]

### Financials
[market_data findings with inline contextual notes where relevant]

### News & Sentiment
[news_macro findings verbatim, preserving all inline citations]

### Filing Analysis
[filings findings verbatim, preserving all citations and red flag table]

### Investment Thesis
**Bull case:** [one sentence - key upside catalyst]
**Bear case:** [one sentence - key downside risk]
**Verdict:** [bullish / bearish / neutral with 1-sentence rationale]

### Sources
[All URLs deduplicated. Yahoo Finance data cited as "Source: Yahoo Finance"]
