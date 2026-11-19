# Corpus provenance

- `darglobal_verified_pages.jsonl` contains concise, source-linked factual excerpts from DarGlobal's public company homepage, project directory, individual project pages, and press releases. Captured on 19 November 2026 from the official pages as returned by the public web index. The local direct HTTP crawler still received an Imperva interstitial and did not bypass it; its result is recorded in `scrape_report.json`.
- `darglobal_quara_news.jsonl` contains DarGlobal headlines discovered on Quara Holding's public news page. Full-text Quara article records from the existing corpus remain in `darglobal.jsonl`.
- `wasalt.jsonl` contains company-profile information from Quara Holding, Wasalt's parent-company profile. It contains no Wasalt listing data.
- `rega_fal_platform_directory.jsonl` contains REGA's public FAL directory entry identifying Wasalt Real Estate Services Company.
- `rega_catalog.jsonl` describes REGA public datasets; it does not contain the datasets' underlying statistics.

No individual Wasalt properties or auction records are included. Wasalt's published terms restrict extraction and copying/republication of its website content. Use an authorized feed or permission before adding that content. No property prices or unit availability have been invented. The decorative landing-page image is generated and is not a real development or listing.
