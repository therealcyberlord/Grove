---
name: analyzing-sentiment
description: Researches recent news, sentiment, and macro context for a stock ticker. Use when the user asks about sentiment, market opinion, news events, analyst commentary, or short-term outlook for a stock.
---

# Analyzing Sentiment

## Procedure

1. Call the news_macro subagent, passing the ticker and user query in the description.
2. Synthesize the response into the output format below.

## Synthesis

Write a focused sentiment report. The executive summary covers: overall sentiment verdict, the primary news driver, and the key risk. 2-3 sentences maximum.

Cite all source URLs inline using markdown links.

## Output format

## {TICKER} - Sentiment Report

### Executive Summary
[2-3 sentences: verdict, primary driver, key risk]

### News & Sentiment
[Subagent findings verbatim, preserving all inline citations]

### Investment Thesis
[Sentiment verdict and primary risk. Narrow scope - based on news only, not financials or filings.]

### Sources
[All URLs deduplicated]
